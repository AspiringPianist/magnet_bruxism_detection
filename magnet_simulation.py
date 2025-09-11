import numpy as np
import magpylib as magpy
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from scipy.signal import welch
from scipy.interpolate import interp1d
from sklearn.metrics import mean_squared_error, mean_absolute_error
import json

# --- 1. Define Magnet and Magnetometer ---
# N35 magnet: 5 mm x 5 mm x 2 mm, magnetization (~1.2 T => 955000 A/m)
magnet = magpy.magnet.Cuboid(
    magnetization=(0, 0, 955000),  # N35 magnetization in A/m (z-axis)
    dimension=(0.005, 0.005, 0.002),  # 5 mm x 5 mm x 2 mm
    position=(0, 0, 0.01)  # Initial position: 10 mm above sensor (jaw closed)
)

# Magnetometer (HMC5883L): Fixed at bottom teeth center (0, 0, 0)
sensor_pos = np.array([0, 0, 0])

# --- 2. Define Jaw Motion Path (Normal + Bruxism) ---
# Simulate 15 seconds at 50 Hz (750 samples)
t = np.linspace(0, 15, 750)  # 15 seconds, 50 Hz
true_positions = []
for ti in t:
    if ti < 5:  # Normal motion (slow lateral, z=10-12 mm)
        x = 0.002 * np.sin(0.5 * ti)  # ±2 mm lateral
        y = 0.002 * np.cos(0.5 * ti)
        z = 0.01 + 0.002 * np.sin(0.5 * ti)  # 10-12 mm
    elif ti < 10:  # Grinding (fast lateral ±5 mm, 1.5 Hz, z=8-10 mm)
        x = 0.005 * np.sin(1.5 * 2 * np.pi * ti)  # 1.5 Hz grinding
        y = 0.005 * np.cos(1.5 * 2 * np.pi * ti)
        z = 0.008 + 0.002 * np.sin(2 * np.pi * ti)
    else:  # Clenching (minimal lateral ±1 mm, z=5-6 mm)
        x = 0.001 * np.sin(0.5 * ti)  # ±1 mm
        y = 0.001 * np.cos(0.5 * ti)
        z = 0.005 + 0.001 * np.sin(0.5 * ti)  # 5-6 mm
    true_positions.append([x, y, z])
true_positions = np.array(true_positions)

# --- 3. Simulate Magnetometer Readings ---
noise_level = 2e-7  # HMC5883L noise: 0.2 µT (2e-7 T)
true_B = []  # True magnetic fields
noisy_B = []  # Noisy measurements

for pos in true_positions:
    magnet.position = pos
    B = magnet.getB(sensor_pos)  # True B-field in tesla
    true_B.append(B)
    noisy_B.append(B + np.random.normal(0, noise_level, 3))  # Add HMC5883L noise

true_B = np.array(true_B)
noisy_B = np.array(noisy_B)

# --- 4. Estimate Magnet Position ---
estimated_positions = []
last_guess = [0, 0, 0.01]  # Initial guess: jaw closed

def objective(pos, measured_B, sensor_pos, magnet):
    """Objective function: Minimize difference between measured and predicted B."""
    magnet.position = pos
    predicted_B = magnet.getB(sensor_pos)
    return np.sum((predicted_B - measured_B) ** 2)

for B_meas in noisy_B:
    result = minimize(
        objective,
        last_guess,
        args=(B_meas, sensor_pos, magnet),
        method='Nelder-Mead',
        options={'maxiter': 2000}
    )
    estimated_positions.append(result.x)
    last_guess = result.x  # Use previous estimate for continuity

estimated_positions = np.array(estimated_positions)

# --- 5. Feature Engineering ---

window_size = 50  # 1 second at 50 Hz
# Features: field magnitude, lateral variance, spectral power, dBx/dz (numerical derivative)
features = {
    'field_magnitude': [],
    'lateral_variance': [],
    'spectral_power': [],
    'dBx_dz': []
}

for i in range(0, len(t) - window_size, window_size):
    window_B = noisy_B[i:i + window_size]
    window_z = true_positions[i:i + window_size, 2]  # z positions
    
    # Field magnitude
    mag = np.sqrt(np.sum(window_B**2, axis=1)) * 1e6  # µT
    features['field_magnitude'].append(np.mean(mag))
    
    # Lateral variance (Bx, By)
    var_Bx = np.var(window_B[:, 0]) * 1e12  # µT²
    var_By = np.var(window_B[:, 1]) * 1e12
    features['lateral_variance'].append((var_Bx + var_By) / 2)
    
    # Spectral power (1-2 Hz)
    freq, psd = welch(window_B[:, 0], fs=50, nperseg=window_size)
    idx = (freq >= 1) & (freq <= 2)
    power = np.sum(psd[idx]) * 1e12  # Scale for visibility
    features['spectral_power'].append(power)

    # ∂Bx/∂z (numerical derivative, µT/mm)
    Bx = window_B[:, 0] * 1e6  # µT
    dz = np.gradient(window_z) * 1000  # mm
    dBx_dz = np.gradient(Bx, dz)
    features['dBx_dz'].append(np.mean(dBx_dz))

# --- 6. Calculate Metrics ---
mse = mean_squared_error(true_positions, estimated_positions) * 1e6  # mm²
mae = mean_absolute_error(true_positions, estimated_positions) * 1e3  # mm
print(f"Mean Squared Error (MSE): {mse:.3f} mm²")
print(f"Mean Absolute Error (MAE): {mae:.3f} mm")

# --- 7. Visualize Results ---
# 7.1: 3D Position Plot
fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection='3d')
ax.plot(true_positions[:, 0] * 1000, true_positions[:, 1] * 1000, true_positions[:, 2] * 1000,
        'b-', label='True Path')
ax.scatter(true_positions[:, 0] * 1000, true_positions[:, 1] * 1000, true_positions[:, 2] * 1000,
           c='blue', s=20, alpha=0.5, label='True Positions')
ax.plot(estimated_positions[:, 0] * 1000, estimated_positions[:, 1] * 1000, estimated_positions[:, 2] * 1000,
        'r--', label='Estimated Path')
ax.scatter([sensor_pos[0] * 1000], [sensor_pos[1] * 1000], [sensor_pos[2] * 1000],
           c='green', s=100, marker='^', label='HMC5883L Magnetometer')
ax.set_xlabel('X (mm)')
ax.set_ylabel('Y (mm)')
ax.set_zlabel('Z (mm)')
ax.set_title('Jaw Tracking for Bruxism: True vs Estimated Positions')
ax.legend()
plt.show()

# Define time indices for each period (for segmented 3D plots)
rest_idx = t < 5  # 0-5 s
grind_idx = (t >= 5) & (t < 10)  # 5-10 s
clench_idx = t >= 10  # 10-15 s

# --- Segmented 3D Position Plots ---
segments = [
    (rest_idx, 'Rest (0-5 s)', 'navy'),
    (grind_idx, 'Grinding (5-10 s)', 'darkred'),
    (clench_idx, 'Clenching (10-15 s)', 'darkgreen')
]
for idx, title, color in segments:
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    ax.plot(true_positions[idx, 0] * 1000, true_positions[idx, 1] * 1000, true_positions[idx, 2] * 1000,
        '-', color=color, label='True Path')
    ax.scatter(true_positions[idx, 0] * 1000, true_positions[idx, 1] * 1000, true_positions[idx, 2] * 1000,
           c=color, s=20, alpha=0.5, label='True Positions')
    ax.plot(estimated_positions[idx, 0] * 1000, estimated_positions[idx, 1] * 1000, estimated_positions[idx, 2] * 1000,
        '--', color='orange', label='Estimated Path')
    ax.scatter([sensor_pos[0] * 1000], [sensor_pos[1] * 1000], [sensor_pos[2] * 1000],
           c='green', s=100, marker='^', label='HMC5883L Magnetometer')
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_zlabel('Z (mm)')
    ax.set_title(f'Jaw Tracking: {title}')
    ax.legend()
    plt.show()

# 7.2: Magnetic Field Plots for Rest, Grinding, Clenching
# Define time indices for each period
rest_idx = t < 5  # 0-5 s
grind_idx = (t >= 5) & (t < 10)  # 5-10 s
clench_idx = t >= 10  # 10-15 s

# Rest Period
plt.figure(figsize=(12, 6))
plt.plot(t[rest_idx], noisy_B[rest_idx, 0] * 1e6, 'b-', label='Bx (lateral)')
plt.plot(t[rest_idx], noisy_B[rest_idx, 1] * 1e6, 'r-', label='By (lateral)')
plt.plot(t[rest_idx], noisy_B[rest_idx, 2] * 1e6, 'g-', label='Bz (vertical)')
plt.xlabel('Time (s)')
plt.ylabel('Magnetic Field (µT)')
plt.title('Magnetic Field During Rest (0-5 s)')
plt.legend()
plt.grid()
plt.show()

# Grinding Period
plt.figure(figsize=(12, 6))
plt.plot(t[grind_idx], noisy_B[grind_idx, 0] * 1e6, 'b-', label='Bx (lateral)')
plt.plot(t[grind_idx], noisy_B[grind_idx, 1] * 1e6, 'r-', label='By (lateral)')
plt.plot(t[grind_idx], noisy_B[grind_idx, 2] * 1e6, 'g-', label='Bz (vertical)')
plt.xlabel('Time (s)')
plt.ylabel('Magnetic Field (µT)')
plt.title('Magnetic Field During Grinding (5-10 s)')
plt.legend()
plt.grid()
plt.show()

# Clenching Period
plt.figure(figsize=(12, 6))
plt.plot(t[clench_idx], noisy_B[clench_idx, 0] * 1e6, 'b-', label='Bx (lateral)')
plt.plot(t[clench_idx], noisy_B[clench_idx, 1] * 1e6, 'r-', label='By (lateral)')
plt.plot(t[clench_idx], noisy_B[clench_idx, 2] * 1e6, 'g-', label='Bz (vertical)')
plt.xlabel('Time (s)')
plt.ylabel('Magnetic Field (µT)')
plt.title('Magnetic Field During Clenching (10-15 s)')
plt.legend()
plt.grid()
plt.show()

# 7.3: Frequency Spectrum Plot
# Compute PSD for Bx in each period
freq_rest, psd_rest = welch(noisy_B[rest_idx, 0], fs=50, nperseg=256)
freq_grind, psd_grind = welch(noisy_B[grind_idx, 0], fs=50, nperseg=256)
freq_clench, psd_grind = welch(noisy_B[clench_idx, 0], fs=50, nperseg=256)

plt.figure(figsize=(12, 6))
plt.plot(freq_rest, psd_rest * 1e12, 'b-', label='Rest (0-5 s)')
plt.plot(freq_grind, psd_grind * 1e12, 'r-', label='Grinding (5-10 s)')
plt.plot(freq_clench, psd_grind * 1e12, 'g-', label='Clenching (10-15 s)')
plt.axvspan(1, 2, alpha=0.2, color='yellow', label='Grinding Frequency (1-2 Hz)')
plt.xlabel('Frequency (Hz)')
plt.ylabel('Power Spectral Density (µT²/Hz)')
plt.title('Frequency Spectrum of Bx for Rest, Grinding, Clenching')
plt.legend()
plt.grid()
plt.xlim(0, 10)  # Focus on low frequencies
plt.show()

# --- Field Magnitude Over Time ---
field_magnitude = np.sqrt(np.sum(noisy_B**2, axis=1)) * 1e6  # µT
plt.figure(figsize=(12, 6))
plt.plot(t, field_magnitude, 'k-')
plt.xlabel('Time (s)')
plt.ylabel('Field Magnitude (µT)')
plt.title('Magnetic Field Magnitude Over Time')
plt.grid()
plt.show()

# --- ∂Bx/∂z Over Time ---
dBx_dz_full = np.gradient(noisy_B[:, 0] * 1e6, true_positions[:, 2] * 1000)  # µT/mm

# --- Save data to JSON ---
# Preprocess data for smooth playback - reduce to 150 points (10Hz equivalent for 15s)
def smooth_resample(data, original_points, target_points):
    """Smoothly resample data from original_points to target_points"""
    from scipy.interpolate import interp1d
    original_indices = np.linspace(0, len(data)-1, original_points)
    target_indices = np.linspace(0, len(data)-1, target_points)
    
    if len(data.shape) == 1:
        # 1D data
        interp_func = interp1d(original_indices, data, kind='cubic')
        return interp_func(target_indices)
    else:
        # 2D data
        result = np.zeros((target_points, data.shape[1]))
        for i in range(data.shape[1]):
            interp_func = interp1d(original_indices, data[:, i], kind='cubic')
            result[:, i] = interp_func(target_indices)
        return result

# Reduce from 750 points to 150 points (10Hz for smooth 15-second playback)
target_points = 150
smooth_t = smooth_resample(t, len(t), target_points)
smooth_positions = smooth_resample(true_positions, len(true_positions), target_points)
smooth_noisy_B = smooth_resample(noisy_B, len(noisy_B), target_points)
smooth_estimated_positions = smooth_resample(estimated_positions, len(estimated_positions), target_points)
smooth_field_magnitude = smooth_resample(field_magnitude, len(field_magnitude), target_points)
smooth_dBx_dz = smooth_resample(dBx_dz_full, len(dBx_dz_full), target_points)

data = {
    't': smooth_t.tolist(),
    'true_positions': smooth_positions.tolist(),
    'noisy_B': smooth_noisy_B.tolist(),
    'estimated_positions': smooth_estimated_positions.tolist(),
    'field_magnitude': smooth_field_magnitude.tolist(),
    'dBx_dz_full': smooth_dBx_dz.tolist(),
    'original_length': len(t),  # Keep track of original data size
    'playback_rate': 100  # Recommended playback interval in ms
}
with open('simulation_data.json', 'w') as f:
    json.dump(data, f)

# --- Visualize Results ---