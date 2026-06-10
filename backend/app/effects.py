import numpy as np
from typing import Optional


class AudioEffect:
    """Base class for all audio effects."""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate

    def process(self, audio: np.ndarray) -> np.ndarray:
        raise NotImplementedError


class GainEffect(AudioEffect):
    """Simple gain adjustment in dB."""

    def __init__(self, sample_rate: int = 44100, gain_db: float = 0.0):
        super().__init__(sample_rate)
        self.gain_db = gain_db

    def process(self, audio: np.ndarray) -> np.ndarray:
        gain_linear = 10 ** (self.gain_db / 20.0)
        return audio * gain_linear


class ParametricEQ(AudioEffect):
    """Parametric equalizer using FFT → frequency domain gain → IFFT."""

    def __init__(self, sample_rate: int = 44100, bands: Optional[list] = None):
        super().__init__(sample_rate)
        # Each band: {"freq": Hz, "gain_db": dB, "q": quality factor}
        self.bands = bands or [
            {"freq": 80, "gain_db": 0.0, "q": 1.0},
            {"freq": 250, "gain_db": 0.0, "q": 1.0},
            {"freq": 1000, "gain_db": 0.0, "q": 1.0},
            {"freq": 4000, "gain_db": 0.0, "q": 1.0},
            {"freq": 12000, "gain_db": 0.0, "q": 1.0},
        ]

    def _build_frequency_response(self, n_fft: int) -> np.ndarray:
        freqs = np.fft.rfftfreq(n_fft, d=1.0 / self.sample_rate)
        gain_curve = np.ones(len(freqs))

        for band in self.bands:
            center_freq = band["freq"]
            gain_db = band["gain_db"]
            q = band["q"]

            if gain_db == 0.0:
                continue

            gain_linear = 10 ** (gain_db / 20.0)
            bandwidth = center_freq / q

            band_mask = np.exp(-0.5 * ((freqs - center_freq) / (bandwidth / 2.0)) ** 2)
            gain_curve *= (1.0 + (gain_linear - 1.0) * band_mask)

        return gain_curve

    def process(self, audio: np.ndarray) -> np.ndarray:
        if audio.ndim == 1:
            return self._process_channel(audio)

        result = np.zeros_like(audio)
        for ch in range(audio.shape[0]):
            result[ch] = self._process_channel(audio[ch])
        return result

    def _process_channel(self, channel: np.ndarray) -> np.ndarray:
        n = len(channel)
        # Use overlap-add with blocks for long audio
        block_size = 4096
        hop_size = block_size // 2
        n_fft = block_size * 2

        gain_curve = self._build_frequency_response(n_fft)

        # Pad input
        padded = np.pad(channel, (0, n_fft))
        output = np.zeros(len(padded))
        window = np.hanning(block_size)

        pos = 0
        while pos < n:
            block = padded[pos:pos + block_size] * window
            spectrum = np.fft.rfft(block, n=n_fft)
            spectrum *= gain_curve
            processed_block = np.fft.irfft(spectrum, n=n_fft)
            output[pos:pos + n_fft] += processed_block
            pos += hop_size

        return output[:n]


class DynamicCompressor(AudioEffect):
    """Dynamic range compressor with envelope detection and gain curve."""

    def __init__(self, sample_rate: int = 44100,
                 threshold_db: float = -20.0,
                 ratio: float = 4.0,
                 attack_ms: float = 5.0,
                 release_ms: float = 50.0,
                 makeup_gain_db: float = 0.0):
        super().__init__(sample_rate)
        self.threshold_db = threshold_db
        self.ratio = ratio
        self.attack_ms = attack_ms
        self.release_ms = release_ms
        self.makeup_gain_db = makeup_gain_db

    def _compute_envelope(self, audio: np.ndarray) -> np.ndarray:
        attack_coeff = np.exp(-1.0 / (self.sample_rate * self.attack_ms / 1000.0))
        release_coeff = np.exp(-1.0 / (self.sample_rate * self.release_ms / 1000.0))

        envelope = np.zeros(len(audio))
        abs_audio = np.abs(audio)

        prev = 0.0
        for i in range(len(audio)):
            if abs_audio[i] > prev:
                prev = attack_coeff * prev + (1.0 - attack_coeff) * abs_audio[i]
            else:
                prev = release_coeff * prev + (1.0 - release_coeff) * abs_audio[i]
            envelope[i] = prev

        return envelope

    def _compute_gain(self, envelope: np.ndarray) -> np.ndarray:
        eps = 1e-10
        envelope_db = 20.0 * np.log10(envelope + eps)

        gain_db = np.zeros_like(envelope_db)
        above_threshold = envelope_db > self.threshold_db

        gain_db[above_threshold] = (
            self.threshold_db +
            (envelope_db[above_threshold] - self.threshold_db) / self.ratio
            - envelope_db[above_threshold]
        )

        gain_db += self.makeup_gain_db
        return 10 ** (gain_db / 20.0)

    def process(self, audio: np.ndarray) -> np.ndarray:
        if audio.ndim == 1:
            return self._process_channel(audio)

        result = np.zeros_like(audio)
        for ch in range(audio.shape[0]):
            result[ch] = self._process_channel(audio[ch])
        return result

    def _process_channel(self, channel: np.ndarray) -> np.ndarray:
        envelope = self._compute_envelope(channel)
        gain = self._compute_gain(envelope)
        return channel * gain


class SimpleReverb(AudioEffect):
    """Simple reverb using multiple delay lines with feedback."""

    def __init__(self, sample_rate: int = 44100,
                 room_size: float = 0.5,
                 damping: float = 0.5,
                 wet_dry: float = 0.3):
        super().__init__(sample_rate)
        self.room_size = room_size
        self.damping = damping
        self.wet_dry = wet_dry

        # Delay line lengths in samples (prime numbers for diffusion)
        base_delays = [1557, 1617, 1491, 1422, 1277, 1356]
        self.delays = [int(d * room_size) for d in base_delays]
        self.feedback = 0.7 * room_size

    def process(self, audio: np.ndarray) -> np.ndarray:
        if audio.ndim == 1:
            return self._process_channel(audio)

        result = np.zeros_like(audio)
        for ch in range(audio.shape[0]):
            result[ch] = self._process_channel(audio[ch])
        return result

    def _process_channel(self, channel: np.ndarray) -> np.ndarray:
        n = len(channel)
        output = np.zeros(n)

        # Comb filters in parallel
        for delay in self.delays:
            comb_out = self._comb_filter(channel, delay, self.feedback, self.damping)
            output += comb_out

        output /= len(self.delays)

        # All-pass filters in series for diffusion
        allpass_delays = [225, 556, 441, 341]
        for delay in allpass_delays:
            output = self._allpass_filter(output, int(delay * self.room_size * 0.5 + 1))

        # Mix dry and wet
        return (1.0 - self.wet_dry) * channel + self.wet_dry * output

    def _comb_filter(self, audio: np.ndarray, delay: int, feedback: float, damping: float) -> np.ndarray:
        n = len(audio)
        output = np.zeros(n)
        buffer = np.zeros(delay)
        buf_idx = 0
        filter_state = 0.0

        for i in range(n):
            buf_out = buffer[buf_idx]
            filter_state = buf_out * (1.0 - damping) + filter_state * damping
            buffer[buf_idx] = audio[i] + filter_state * feedback
            output[i] = buf_out
            buf_idx = (buf_idx + 1) % delay

        return output

    def _allpass_filter(self, audio: np.ndarray, delay: int) -> np.ndarray:
        n = len(audio)
        output = np.zeros(n)
        buffer = np.zeros(delay)
        buf_idx = 0
        gain = 0.5

        for i in range(n):
            buf_out = buffer[buf_idx]
            output[i] = -audio[i] + buf_out
            buffer[buf_idx] = audio[i] + buf_out * gain
            buf_idx = (buf_idx + 1) % delay

        return output


class SpectralNoiseReduction(AudioEffect):
    """Noise reduction using spectral subtraction."""

    def __init__(self, sample_rate: int = 44100,
                 noise_reduction_db: float = 12.0,
                 noise_floor_db: float = -60.0,
                 smoothing: float = 0.9):
        super().__init__(sample_rate)
        self.noise_reduction_db = noise_reduction_db
        self.noise_floor_db = noise_floor_db
        self.smoothing = smoothing
        self.noise_profile = None

    def estimate_noise(self, noise_audio: np.ndarray, n_fft: int = 2048):
        """Estimate noise profile from a noise-only segment."""
        hop = n_fft // 2
        window = np.hanning(n_fft)
        n_frames = (len(noise_audio) - n_fft) // hop + 1

        if n_frames <= 0:
            self.noise_profile = np.zeros(n_fft // 2 + 1)
            return

        noise_spectrum = np.zeros(n_fft // 2 + 1)
        for i in range(n_frames):
            frame = noise_audio[i * hop:i * hop + n_fft] * window
            spectrum = np.abs(np.fft.rfft(frame))
            noise_spectrum += spectrum ** 2

        self.noise_profile = np.sqrt(noise_spectrum / n_frames)

    def process(self, audio: np.ndarray) -> np.ndarray:
        if audio.ndim == 1:
            return self._process_channel(audio)

        result = np.zeros_like(audio)
        for ch in range(audio.shape[0]):
            result[ch] = self._process_channel(audio[ch])
        return result

    def _process_channel(self, channel: np.ndarray) -> np.ndarray:
        n_fft = 2048
        hop = n_fft // 2
        window = np.hanning(n_fft)
        n = len(channel)

        # If no noise profile, estimate from first 0.5s
        if self.noise_profile is None:
            noise_samples = min(int(0.5 * self.sample_rate), n)
            self.estimate_noise(channel[:noise_samples], n_fft)

        reduction_factor = 10 ** (self.noise_reduction_db / 20.0)
        floor_level = 10 ** (self.noise_floor_db / 20.0)

        # Overlap-add processing
        padded = np.pad(channel, (0, n_fft))
        output = np.zeros(len(padded))
        prev_magnitude = None

        pos = 0
        while pos + n_fft <= len(padded):
            frame = padded[pos:pos + n_fft] * window
            spectrum = np.fft.rfft(frame)
            magnitude = np.abs(spectrum)
            phase = np.angle(spectrum)

            # Spectral subtraction
            clean_magnitude = magnitude - reduction_factor * self.noise_profile
            clean_magnitude = np.maximum(clean_magnitude, floor_level * magnitude)

            # Temporal smoothing
            if prev_magnitude is not None:
                clean_magnitude = self.smoothing * prev_magnitude + (1.0 - self.smoothing) * clean_magnitude
            prev_magnitude = clean_magnitude

            clean_spectrum = clean_magnitude * np.exp(1j * phase)
            frame_out = np.fft.irfft(clean_spectrum, n=n_fft)
            output[pos:pos + n_fft] += frame_out * window
            pos += hop

        # Normalize overlap-add
        norm = np.zeros(len(padded))
        pos = 0
        while pos + n_fft <= len(padded):
            norm[pos:pos + n_fft] += window ** 2
            pos += hop
        norm = np.maximum(norm, 1e-8)
        output /= norm

        return output[:n]


EFFECT_REGISTRY = {
    "gain": {
        "class": GainEffect,
        "default_params": {"gain_db": 0.0},
        "name": "增益",
        "description": "调整音量增益 (dB)"
    },
    "eq": {
        "class": ParametricEQ,
        "default_params": {
            "bands": [
                {"freq": 80, "gain_db": 0.0, "q": 1.0},
                {"freq": 250, "gain_db": 0.0, "q": 1.0},
                {"freq": 1000, "gain_db": 0.0, "q": 1.0},
                {"freq": 4000, "gain_db": 0.0, "q": 1.0},
                {"freq": 12000, "gain_db": 0.0, "q": 1.0},
            ]
        },
        "name": "参数均衡器",
        "description": "FFT频域增益均衡"
    },
    "compressor": {
        "class": DynamicCompressor,
        "default_params": {
            "threshold_db": -20.0,
            "ratio": 4.0,
            "attack_ms": 5.0,
            "release_ms": 50.0,
            "makeup_gain_db": 0.0
        },
        "name": "动态压缩器",
        "description": "包络检测+增益压缩"
    },
    "reverb": {
        "class": SimpleReverb,
        "default_params": {
            "room_size": 0.5,
            "damping": 0.5,
            "wet_dry": 0.3
        },
        "name": "混响",
        "description": "延迟线+反馈混响"
    },
    "noise_reduction": {
        "class": SpectralNoiseReduction,
        "default_params": {
            "noise_reduction_db": 12.0,
            "noise_floor_db": -60.0,
            "smoothing": 0.9
        },
        "name": "降噪",
        "description": "谱减法降噪"
    }
}


def create_effect(effect_type: str, sample_rate: int, params: dict) -> AudioEffect:
    if effect_type not in EFFECT_REGISTRY:
        raise ValueError(f"Unknown effect type: {effect_type}")

    effect_info = EFFECT_REGISTRY[effect_type]
    effect_class = effect_info["class"]
    return effect_class(sample_rate=sample_rate, **params)


def process_chain(audio: np.ndarray, sample_rate: int, nodes: list) -> np.ndarray:
    """Process audio through a chain of effects."""
    result = audio.copy()
    for node in nodes:
        if not node.get("enabled", True):
            continue
        effect = create_effect(node["effect_type"], sample_rate, node.get("params", {}))
        result = effect.process(result)
    return result


def compute_fft_spectrum(audio: np.ndarray, sample_rate: int, n_fft: int = 2048) -> dict:
    """Compute FFT magnitude spectrum for visualization."""
    if audio.ndim > 1:
        audio = audio[0]

    if len(audio) < n_fft:
        audio = np.pad(audio, (0, n_fft - len(audio)))

    window = np.hanning(n_fft)
    windowed = audio[:n_fft] * window
    spectrum = np.fft.rfft(windowed)
    magnitude = np.abs(spectrum)
    magnitude_db = 20 * np.log10(magnitude + 1e-10)
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)

    return {
        "frequencies": freqs.tolist(),
        "magnitude_db": magnitude_db.tolist()
    }


def compute_spectrogram(audio: np.ndarray, sample_rate: int,
                        n_fft: int = 2048, hop: int = 512) -> dict:
    """Compute spectrogram for visualization."""
    if audio.ndim > 1:
        audio = audio[0]

    window = np.hanning(n_fft)
    n_frames = (len(audio) - n_fft) // hop + 1

    if n_frames <= 0:
        return {"times": [], "frequencies": [], "magnitude_db": []}

    # Limit to max 500 frames for transport
    max_frames = 500
    actual_hop = hop
    if n_frames > max_frames:
        actual_hop = (len(audio) - n_fft) // max_frames
        n_frames = max_frames

    spectrogram = np.zeros((n_fft // 2 + 1, n_frames))
    for i in range(n_frames):
        start = i * actual_hop
        frame = audio[start:start + n_fft] * window
        spectrum = np.abs(np.fft.rfft(frame))
        spectrogram[:, i] = spectrum

    magnitude_db = 20 * np.log10(spectrogram + 1e-10)
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
    times = np.arange(n_frames) * actual_hop / sample_rate

    return {
        "times": times.tolist(),
        "frequencies": freqs.tolist(),
        "magnitude_db": magnitude_db.tolist()
    }
