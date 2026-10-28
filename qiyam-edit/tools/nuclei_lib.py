"""Syllable-nucleus detection from the speech track (energy peaks)."""
import numpy as np, librosa
from scipy.signal import butter, sosfiltfilt, find_peaks

def nuclei(path, sr=16000):
    y, _ = librosa.load(path, sr=sr)
    b = sosfiltfilt(butter(4, [300, 3000], btype="band", fs=sr, output="sos"), y)
    hop = 80
    env = np.sqrt(np.convolve(b ** 2, np.ones(hop * 4) / (hop * 4), mode="same"))[::hop]
    env = librosa.amplitude_to_db(env + 1e-6)
    sm = sosfiltfilt(butter(2, 10, btype="low", fs=200, output="sos"), env)
    pk, _ = find_peaks(sm, distance=int(0.11 * 200), prominence=2.5)
    keep = sm[pk] > np.percentile(sm, 35)
    return pk[keep] / 200.0, sm
