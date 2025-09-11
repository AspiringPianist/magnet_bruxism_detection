import serial
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import time
import csv
import os

# --- Configuration ---
SERIAL_PORT = 'COM3'  # <--- CHANGE THIS to your Arduino's port
BAUD_RATE = 9600
CALIBRATION_FILENAME = 'magnetometer_calibration.npz'

# --- STAGE 1: SENSOR CALIBRATION ---

def collect_calibration_data(duration_s=30):
    """Connects to serial, guides user, and collects raw data for sensor calibration."""
    print("--- Sensor Calibration: Step 1: Data Collection ---")
    print("IMPORTANT: Ensure the target magnet is FAR AWAY from the sensor for this step.")
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        time.sleep(2)
    except serial.SerialException as e:
        print(f"\n[ERROR] Could not open serial port '{SERIAL_PORT}': {e}")
        return None, None

    input("\nSerial port connected. When ready to begin rotating the sensor, press Enter...")
    
    print(f"\nStarting data collection for {duration_s} seconds.")
    print("ACTION: Slowly rotate the sensor in all possible directions (figure-eight motions).")
    
    raw_data = []
    start_time = time.time()
    ser.reset_input_buffer()

    while time.time() - start_time < duration_s:
        try:
            line = ser.readline().decode('utf-8').strip()
            if line:
                parts = line.split(',')
                if len(parts) == 3:
                    raw_data.append([float(p) for p in parts])
            
            elapsed = time.time() - start_time
            progress = int((elapsed / duration_s) * 20)
            print(f"Collecting... [{'#' * progress}{' ' * (20 - progress)}] {int(elapsed)}s", end='\r')

        except (ValueError, UnicodeDecodeError):
            continue
        except KeyboardInterrupt:
            print("\nData collection stopped by user.")
            break
            
    print("\n\nData collection complete.")
    return np.array(raw_data), ser

def calculate_and_save_calibration(data):
    """Calculates calibration parameters and saves them to a file."""
    print("\n--- Sensor Calibration: Step 2: Calculating and Saving Parameters ---")
    if data is None or len(data) < 50:
        print("[ERROR] Not enough data for calibration.")
        return None, None

    # Hard-Iron Correction
    min_vals, max_vals = np.min(data, axis=0), np.max(data, axis=0)
    hard_iron_offset = (max_vals + min_vals) / 2.0
    
    # Soft-Iron Correction
    centered_data = data - hard_iron_offset
    D = np.array([
        centered_data[:, 0]**2, centered_data[:, 1]**2, centered_data[:, 2]**2,
        2 * centered_data[:, 0] * centered_data[:, 1],
        2 * centered_data[:, 0] * centered_data[:, 2],
        2 * centered_data[:, 1] * centered_data[:, 2],
    ]).T
    v = np.linalg.lstsq(D, np.ones(len(centered_data)), rcond=None)[0]
    M = np.array([[v[0], v[3], v[4]], [v[3], v[1], v[5]], [v[4], v[5], v[2]]])
    eig_vals, eig_vecs = np.linalg.eigh(M)
    soft_iron_matrix = eig_vecs @ np.sqrt(np.diag(eig_vals)) @ eig_vecs.T
    
    print(f"Hard-Iron Offset: {hard_iron_offset}")
    print("Soft-Iron Matrix:")
    print(soft_iron_matrix)
    
    # Save parameters to a file for later use
    np.savez(CALIBRATION_FILENAME, offset=hard_iron_offset, matrix=soft_iron_matrix)
    print(f"\nCalibration parameters saved to '{CALIBRATION_FILENAME}'.")
    
    return hard_iron_offset, soft_iron_matrix

def visualize_calibration(raw_data, offset, matrix):
    """Creates a 3D plot to show the 'before' and 'after' of sensor calibration."""
    calibrated_data = (raw_data - offset) @ matrix
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection='3d')
    ax.scatter(raw_data[:, 0], raw_data[:, 1], raw_data[:, 2], c='r', marker='.', label='Raw Sensor Data')
    ax.scatter(calibrated_data[:, 0], calibrated_data[:, 1], calibrated_data[:, 2], c='b', marker='.', label='Calibrated Sensor Data')
    ax.set_title('Sensor Calibration Results')
    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
    ax.legend()
    ax.axis('equal')
    print("\nDisplaying 3D plot. Red=distorted, Blue=corrected sphere. Close plot to continue.")
    plt.show()

# --- STAGE 2: LIVE TRACKING ---

def apply_calibration(raw_reading, offset, matrix):
    """Applies pre-calculated calibration to a single reading."""
    return (np.array(raw_reading) - offset) @ matrix

def live_tracking_demo(ser, offset, matrix):
    """
    Demonstrates live tracking for a coupled system like jaw tracking.
    It measures movement relative to a starting reference pose.
    """
    print("\n--- Live Jaw Tracking Demo ---")
    
    # Step 1: Capture Reference Pose
    input(
        "\nACTION: Put on the device and hold your jaw in a comfortable, "
        "fixed 'reference' position (e.g., teeth gently closed). \n"
        "Press Enter to capture this position as your zero point..."
    )
    
    print("Capturing reference position for 3 seconds... Hold still.")
    reference_readings = []
    start_time = time.time()
    ser.reset_input_buffer()
    while time.time() - start_time < 3:
        try:
            line = ser.readline().decode('utf-8').strip()
            if line:
                parts = line.split(',')
                if len(parts) == 3:
                    raw_reading = [float(p) for p in parts]
                    calibrated_reading = apply_calibration(raw_reading, offset, matrix)
                    reference_readings.append(calibrated_reading)
        except (ValueError, UnicodeDecodeError):
            continue
    
    if not reference_readings:
        print("[ERROR] Failed to capture reference pose. Check connection.")
        return
        
    # The reference field is the average of the readings at the start position.
    reference_baseline = np.mean(reference_readings, axis=0)
    print(f"Reference Pose Captured. Baseline Field: {reference_baseline}")
    
    # Step 2: Track Movement Relative to the Reference Pose
    print("\nACTION: You can now move your jaw.")
    print("The script will show the CHANGE in the magnetic field from your starting pose.")
    print("Press Ctrl+C to stop.")
    
    try:
        while True:
            line = ser.readline().decode('utf-8').strip()
            if line:
                parts = line.split(',')
                if len(parts) == 3:
                    raw_reading = [float(p) for p in parts]
                    
                    # Apply corrections in real-time
                    calibrated_reading = apply_calibration(raw_reading, offset, matrix)
                    
                    # Calculate the delta from the reference pose
                    field_delta = calibrated_reading - reference_baseline
                    
                    # This delta is the input for your position-solving algorithm
                    print(f"Field Change (dX,dY,dZ): {field_delta[0]:>8.2f}, {field_delta[1]:>8.2f}, {field_delta[2]:>8.2f}", end='\r')
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\n\nLive tracking stopped.")
    except serial.SerialException:
        print("\n[ERROR] Serial device disconnected.")
    finally:
        if ser and ser.is_open:
            ser.close()


def main():
    """Main function to run the calibration and tracking process."""
    offset, matrix = None, None
    
    # Try to load existing calibration
    if os.path.exists(CALIBRATION_FILENAME):
        use_existing = input(f"Found '{CALIBRATION_FILENAME}'. Use these parameters? (y/n): ").lower()
        if use_existing == 'y':
            with np.load(CALIBRATION_FILENAME) as data:
                offset = data['offset']
                matrix = data['matrix']
            print("Loaded existing calibration parameters.")
    
    # If no calibration exists or user wants to re-calibrate
    if offset is None:
        raw_data, ser_conn = collect_calibration_data()
        if raw_data is not None:
            offset, matrix = calculate_and_save_calibration(raw_data)
            visualize_calibration(raw_data, offset, matrix)
        if ser_conn and ser_conn.is_open:
            ser_conn.close() # Close connection after calibration
    
    if offset is None:
        print("\nCould not obtain calibration parameters. Exiting.")
        return

    # Proceed to live tracking demo
    start_live = input("\nProceed to live tracking demo? (y/n): ").lower()
    if start_live == 'y':
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
            time.sleep(2)
            live_tracking_demo(ser, offset, matrix)
        except serial.SerialException as e:
            print(f"\n[ERROR] Could not open serial port for live tracking: {e}")

if __name__ == '__main__':
    main()