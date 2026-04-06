# -*- coding: utf-8 -*-

import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from scipy.signal import savgol_filter
import time
import configparser
from scipy.signal import find_peaks
from datetime import datetime
import tkinter as tk 
from tkinter.filedialog import askdirectory 
import peakutils
import csv
import math
#import win32api
#import win32com.client
from matplotlib.animation import FFMpegWriter
import sqlite3 as sq
from utils import interactive_code
from agent import auto_select_peaks, Watchdog, agent_reselect
# import torch
# import torch.nn as nn
# import joblib
from collections import OrderedDict

# # --------------------- Model Architecture ---------------------
# class VelocityTempModel(nn.Module):
#     def __init__(self, num_wgs, embedding_dim=8):
#         super().__init__()
#         self.embed = nn.Embedding(num_wgs, embedding_dim)
#         self.net = nn.Sequential(
#             nn.Linear(embedding_dim + 2, 256),
#             nn.ReLU(),
#             nn.Linear(256, 128),
#             nn.ReLU(),
#             nn.Linear(128, 2)
#         )
#     def forward(self, wg_id, cont_feats):
#         wg_embed = self.embed(wg_id)
#         x = torch.cat([wg_embed, cont_feats], dim=1)
#         return self.net(x)
    


# # --------------------- Real-Time Prediction Function ---------------------
# def predict_temperature(gtof_value:float, waveguide_name:str, l1_value:float,xscaler_loc:str,yscaler_loc:str,encoder_loc:str,model_loc:str):
#     # --------------------- Setup ---------------------
#     device = torch.device("cpu")
#     print(" Loading model and scalers...")
#     x_scaler = joblib.load(xscaler_loc)
#     y_scaler = joblib.load(yscaler_loc)
#     le = joblib.load(encoder_loc)
#     num_waveguides = len(le.classes_)
#     model = VelocityTempModel(num_wgs=num_waveguides)
#     state_dict = torch.load(
#         model_loc,
#         map_location=device
#     )
#     # Clean up DataParallel keys
#     new_state_dict = OrderedDict()
#     for k, v in state_dict.items():
#         new_state_dict[k.replace("module.", "")] = v
#     model.load_state_dict(new_state_dict, strict=False)
#     model = model.to(device)
#     model.eval()
#     print("Model ready for real-time predictions.")
#     """Predict temperature (°C) and velocity for a single GToF input."""
#     if waveguide_name not in le.classes_:
#         raise ValueError(f"Waveguide '{waveguide_name}' not found. Available: {list(le.classes_)}")
#     wg_id = le.transform([waveguide_name])[0]
#     cont_input = np.array([[gtof_value, l1_value]], dtype=np.float32)
#     cont_scaled = x_scaler.transform(cont_input)
#     wg_tensor = torch.tensor([wg_id], dtype=torch.long, device=device)
#     cont_tensor = torch.tensor(cont_scaled, dtype=torch.float32, device=device)
#     with torch.no_grad():
#         output = model(wg_tensor, cont_tensor).cpu().numpy()
#         pred_velocity, pred_temp = y_scaler.inverse_transform(output)[0]
#     return pred_velocity, pred_temp

# s1_xscaler_loc = r"models\s1_x_scaler.pkl"
# s1_yscaler_loc = r"models\s1_y_scaler.pkl"
# s1_encoder_loc = r"models\s1_label_encoder.pkl"
# s1_model_loc = r"models\s1_velocity_tc_model.pth"

# s2_xscaler_loc = r"models\s2_x_scaler.pkl"
# s2_yscaler_loc = r"models\s2_y_scaler.pkl"
# s2_encoder_loc = r"models\s2_label_encoder.pkl"
# s2_model_loc = r"models\s2_velocity_tc_model.pth"

con = sq.connect('Tof_data.db')

def interactive_code(y, limit):
    fig, ax = plt.subplots()
    
    ax.set_title('Peak & valley track')
    ax.set_xlabel('Time(s)')
    ax.set_ylabel('Amplitude')

    # Foreground plot (interactive)
    line, = ax.plot(y, picker=True, pickradius=3, color='b',
                    label='Current', zorder=2)

    # dt = 1 / 250
    picks = []              # store (idx, amp)
    markers = []            # store marker artists
    vlines_per_pick = []    # store vline artists for each pick

    def onpick(event):
        if event.artist != line:  # only respond to main line
            return
        if len(picks) >= limit:
            print("Selection limit reached.")
            return

        idx = int(event.ind[0])
        amp = y[idx]
        picks.append((idx, amp))

        # Plot marker and vertical lines
        m = ax.plot(idx, amp, "rx", zorder=3)[0]
        vls = []
        vls.append(ax.vlines(idx - 100, amp - 1, amp + 1,
                             linestyles="dashed", color="k", zorder=2))
        vls.append(ax.vlines(idx + 100, amp - 1, amp + 1,
                             linestyles="dashed", color="m", zorder=2))

        # expected = ((idx * dt) + ex) * 250
        # vls.append(ax.vlines(expected, amp - 1, amp + 1,
        #                      linestyles="dashed", color="g", zorder=2))

        # pick_num = len(picks)
        # if pick_num == 2:
        #     vls.append(ax.vlines(((idx * dt) + tor_ex) * 250,
        #                          amp - 1, amp + 1,
        #                          linestyles="dashed", color="black", zorder=2))
        # elif pick_num == 4:
        #     vls.append(ax.vlines(((idx * dt) + 1100) * 250,
        #                          amp - 1, amp + 1,
        #                          linestyles="dashed", color="black", zorder=2))

        markers.append(m)
        vlines_per_pick.append(vls)

        fig.canvas.draw_idle()

        if len(picks) == limit:
            fig.canvas.mpl_disconnect(cid)
            fig.canvas.mpl_disconnect(kid)
            print("Event handlers disconnected")

    def on_key(event):
        if event.key and event.key.lower() == "z" and picks:
            idx, amp = picks.pop()
            print(f"Removed: {idx}, {amp}")

            # Remove marker
            m = markers.pop()
            m.remove()

            # Remove vlines
            vls = vlines_per_pick.pop()
            for vl in vls:
                vl.remove()

            fig.canvas.draw_idle()

    cid = fig.canvas.mpl_connect("pick_event", onpick)
    kid = fig.canvas.mpl_connect("key_press_event", on_key)

    ax.legend()
    plt.show()

    # refine indices
    indices = []
    for idx, _ in picks:
        start, end = max(idx - 100, 0), min(idx + 100, len(y))
        indices.append(np.argmax(y[start:end]) + start)

    return indices



# Read from config file
config = configparser.ConfigParser()
p = os.path.join(os.path.dirname(__file__), 'Rio-Tinto new.ini')
config.read(p)

OutputDest = config['PATH']['Outputdest']
Result = config['PATH']['Result']
samplefreq_in_MHz = int(config['THRESHOLDS']['samplefreq_in_MHz'])
#Amplitude_Threshold = float(config['THRESHOLDS']['Amplitude_Threshold'])
#Distance = int(config['THRESHOLDS']['Distance'])
#Trigger = int(config['THRESHOLDS']['Trigger'])
# Left Constants
L0_1          =  float(config['CONSTANTS']['L0_1'])
L0_2          =  float(config['CONSTANTS']['L0_2'])


Alpha        =  float(config['CONSTANTS']['Alpha'])


T0        =  int(config['CONSTANTS']['T0'])

M1        =  float(config['VELOCITY COEFFICIENTS']['M1'])
N1        =  float(config['VELOCITY COEFFICIENTS']['N1'])
P1        =  float(config['VELOCITY COEFFICIENTS']['P1'])

M2        =  float(config['VELOCITY COEFFICIENTS']['M2'])
N2        =  float(config['VELOCITY COEFFICIENTS']['N2'])
P2        =  float(config['VELOCITY COEFFICIENTS']['P2'])

L0_3          =  float(config['CONSTANTS']['L0_3'])
L0_4          =  float(config['CONSTANTS']['L0_4'])

gauge_lengths = [L0_1, L0_2, L0_3, L0_4]

watchdog = Watchdog(
    gauge_lengths_um=gauge_lengths,
    sample_freq_mhz=samplefreq_in_MHz,
    velocity_coeffs=(M1, N1, P1),
    max_gate_shift=200,       # samples — tune this per site
    min_amplitude=0.1,        # volts — tune per transducer
    temp_range=(-50, 1500),   # °C — adjust for Rio Tinto furnace range
)

#samp_freq= 500 #Sampling Frequency in MHz
dt = 1/samplefreq_in_MHz  # Sampling time



sen_peaks = pd.DataFrame(columns=['Ascan File No.', 'peak1', 'peak2', 'peak3', 'peak4','peak5','peak6'])
sen_peaks1 = pd.DataFrame(columns=['Ascan File No.', 'peak1', 'peak2', 'peak3', 'peak4','peak5','peak6'])

isEmpty = 1
root = tk.Tk()
root.withdraw()


TOF_df = pd.DataFrame(columns=['Ascan File No.','Creation_Time'])
current_directory = askdirectory()

i = 2


try:
    file_path = os.path.join(current_directory, f"1 ({i}).csv")
    if not os.path.isfile(file_path):
        print(f"{i}th file does not exist")
        raise Exception
    
    # data = pd.read_csv(file_path, sep=',', on_bad_lines='skip', index_col=False, dtype='unicode')
    
    data = pd.read_csv(file_path, sep=',', index_col=False, dtype='unicode')
    a= data[3:]['average(A)']
    a = a.replace('∞',0)
    a = a.replace('-∞',0)
    Trigger = 0
    n = len(a)
    #n= 140000
    ydash1 = a.values.ravel()
    y1 = savgol_filter(ydash1, 61, 3)
    y2 = savgol_filter(y1, 61, 3)
    

    data2 = y2[Trigger:n]

    # peaks, _ = find_peaks(data2, height=1.61, distance=500)


    # selected_peaks = peaks[[0,1,2]]
    # selected_peaks = interactive_code(data2,5)
    selected_peaks = auto_select_peaks(
        waveform=data2,
        num_peaks=5,
        sample_freq_mhz=samplefreq_in_MHz,
        gauge_lengths_um=gauge_lengths,
        min_height=0.3,       # adjust based on your typical echo amplitude
        min_distance=500,     # minimum samples between notch echoes
    )

    
    # valley, _ = find_peaks(-data2, height=2.18, distance=800)
    # selected_valley = valley[[0,3,5,6]]

    gate=500
    
    #peak
    ##################################################

    Start_P11 = (selected_peaks[0]-gate) + Trigger
    End_P11 = (selected_peaks[0]+gate) + Trigger

    Start_P12 = (selected_peaks[1]-gate) + Trigger
    End_P12 = (selected_peaks[1]+gate) + Trigger

    Start_P13 = (selected_peaks[2]-gate) + Trigger
    End_P13 = (selected_peaks[2]+gate) + Trigger

    Start_P14 = (selected_peaks[3]-gate) + Trigger
    End_P14 = (selected_peaks[3]+gate) + Trigger

    Start_P15 = (selected_peaks[4]-gate) + Trigger
    End_P15 = (selected_peaks[4]+gate) + Trigger

    
   
    #################################################
    
    
     
except:
    print("Error in first file")

fig = plt.figure(figsize=(16, 8))


plt.rcParams['animation.ffmpeg_path'] = r"ffmpeg copy.exe"
metadata = dict(title='Rio-Tinto', artist='Matplotlib',comment='Movie support!')


writers = FFMpegWriter(fps=10, metadata=metadata)

try:
    with writers.saving(fig,Result +"/"+"Rio-Tinto_Cal_T4.mp4", 100):
        while True:
            isFile = 0  # 0- is not a file 1- is a file
            while isEmpty == 1:
                file_name1 = "1 (%s).csv"
                file_path1 = os.path.join(current_directory, file_name1)
                next_file = file_path1 % str(i)
                try:
                    f = os.path.isfile(next_file)
                    if f == True:
                        isFile = 1
                    
                    try:
                        df = pd.read_csv(next_file, engine='python')
                        # print("(%s) exists. Making isEmpty=1" % next_file)
                        isEmpty = 0
                        # print("yaay file found")
                    except pd.errors.EmptyDataError:
                        print("file %s is empty" % ("1 (" + str(i) +").csv"))
                        # time.sleep(1)
                except:
                    # print("file not found")
                    time.sleep(12)
            isEmpty = 1

            if True:
 
                file_name = "1 (%d).csv" 
                file_path = os.path.join(current_directory, file_name)
                # data1 = pd.read_csv(file_path % i, sep=',', on_bad_lines='skip', index_col=False, dtype='unicode')
                try:
                    # freqqq = []
                    data1 = pd.read_csv(file_path % i, sep=',', index_col=False, dtype='unicode')
                    a = data1[3:]['average(A)']
                    a = a.replace('∞',0)
                    a = a.replace('-∞',0)
                    
                    ##################################
                    
                    max_index11 = np.argmax(savgol_filter(savgol_filter(a.values.ravel()[Start_P11:End_P11],61,3),61,3))
                    max_index12 = np.argmax(savgol_filter(savgol_filter(a.values.ravel()[Start_P12:End_P12],61,3),61,3))
                    max_index13 = np.argmax(savgol_filter(savgol_filter(a.values.ravel()[Start_P13:End_P13],61,3),61,3))
                    max_index14 = np.argmax(savgol_filter(savgol_filter(a.values.ravel()[Start_P14:End_P14],61,3),61,3))
                    max_index15 = np.argmax(savgol_filter(savgol_filter(a.values.ravel()[Start_P15:End_P15],61,3),61,3))

                    a = a.to_numpy(dtype=np.float64)
                    n = len(a)
                    
                    ydash1 = a.ravel()
                    
                    indexes = [Start_P11 + max_index11,Start_P12 + max_index12,Start_P13 + max_index13,Start_P14 + max_index14,Start_P15 + max_index15]
                    interpolatedIndexes = peakutils.interpolate(np.array(list(range(0, len(ydash1)))), ydash1, ind=indexes)

                    
                    ######################################
                    
                    TOR1 = (max_index11+Start_P11)*dt
                    TOR2 = (max_index12+Start_P12)*dt
                    TOR3 = (max_index13+Start_P13)*dt
                    TOR4 = (max_index14+Start_P14)*dt
                    TOR5 = (max_index15+Start_P15)*dt

                    ######################################################
                    
                    
                    TOF_1 =  ((max_index12+Start_P12) - (max_index11+Start_P11))*dt
                    TOF_2 = ((max_index13+Start_P13) - (max_index12+Start_P12))*dt
                    TOF_3 = ((max_index14+Start_P14) - (max_index13+Start_P13))*dt
                    TOF_4 = ((max_index15+Start_P15) - (max_index14+Start_P14))*dt
                    
                    
                    #############################################################
                
                    GG1 = (interpolatedIndexes[0])*dt
                    GG2 = (interpolatedIndexes[1])*dt
                    GG3 = (interpolatedIndexes[2])*dt
                    GG4 = (interpolatedIndexes[3])*dt
                    GG5 = (interpolatedIndexes[4])*dt

                    ###########################################################
                    
                    gtof1 = (interpolatedIndexes[1] - interpolatedIndexes[0])*dt
                    gtof2 = (interpolatedIndexes[2] - interpolatedIndexes[1])*dt
                    gtof3 = (interpolatedIndexes[3] - interpolatedIndexes[2])*dt
                    gtof4 = (interpolatedIndexes[4] - interpolatedIndexes[3])*dt

                    #############################################################

                    P_Amp1 = a[Start_P11+max_index11]
                    P_Amp2 = a[Start_P12+max_index12]
                    P_Amp3 = a[Start_P13+max_index13]
                    P_Amp4 = a[Start_P14+max_index14]
                    P_Amp5 = a[Start_P15+max_index15]

                    p = os.path.join(os.path.dirname(__file__), 'Rio-Tinto new.ini')
                    config.read(p)

                    M1 = float(config['VELOCITY COEFFICIENTS']['M1'])
                    N1 = float(config['VELOCITY COEFFICIENTS']['N1'])
                    P1 = float(config['VELOCITY COEFFICIENTS']['P1'])
                    
                    Alpha = float(config['CONSTANTS']['Alpha'])
                    T0 = int(config['CONSTANTS']['T0'])
                    L0_1 = float(config['CONSTANTS']['L0_1'])
                    L0_2 = float(config['CONSTANTS']['L0_2'])
                    L0_3 = float(config['CONSTANTS']['L0_3'])
                    L0_4 = float(config['CONSTANTS']['L0_4'])

                        

# #-------------------------------------------------------------------------------------------------------------------------------
                    # Calculate coefficients for Sensor 1
                    a_1 = M1
                    b_1 = N1 - ((2 * L0_1 * Alpha) / gtof1)
                    c_1 = P1 + ((2 * L0_1 * (Alpha * T0 - 1)) / gtof1)

                    # Solve quadratic equation for Sensor 1
                    d_1 = b_1**2 - 4 * a_1 * c_1  # Discriminant

                    if d_1 < 0:
                        print("Sensor 1: This equation has no real solution")
                        x1_1 = x1_2 = 0
                        
                    elif d_1 == 0:
                        x1_1 = x1_2 = -b_1 / (2 * a_1)
                        print("Sensor 1: This equation has one solution: x1 =", x1_1)
                        
                    else:
                        x1_1 = (-b_1 + math.sqrt(d_1)) / (2 * a_1)
                        x1_2 = (-b_1 - math.sqrt(d_1)) / (2 * a_1)
                        print("Sensor 1: This equation has two solutions: x1_1 =", x1_1, "or x1_2 =", x1_2)
# -------------------------------------------------------------------------------------------------------------------------------
                    # Calculate coefficients for Sensor 2
                    a_2 = M1
                    b_2 = N1 - ((2 * L0_2 * Alpha) / gtof2)
                    c_2 = P1 + ((2 * L0_2 * (Alpha * T0 - 1)) / gtof2)

                    # Solve quadratic equation for Sensor 2
                    d_2 = b_2**2 - 4 * a_2 * c_2  # Discriminant

                    if d_2 < 0:
                        print("Sensor 2: This equation has no real solution")
                        x2_1 = x2_2 = 0

                    elif d_2 == 0:
                        x2_1 = x2_2 = -b_2 / (2 * a_2)
                        print("Sensor 2: This equation has one solution: x2 =", x2_1)

                    else:
                        x2_1 = (-b_2 + math.sqrt(d_2)) / (2 * a_2)
                        x2_2 = (-b_2 - math.sqrt(d_2)) / (2 * a_2)
                        print("Sensor 2: This equation has two solutions: x2_1 =", x2_1, "or x2_2 =", x2_2)
# # -------------------------------------------------------------------------------------------------------------------------------
                    # Calculate coefficients for Sensor 3
                    a_3 = M1
                    b_3 = N1 - ((2 * L0_3 * Alpha) / gtof3)
                    c_3 = P1 + ((2 * L0_3 * (Alpha * T0 - 1)) / gtof3)

                    # Solve quadratic equation for Sensor 3
                    d_3 = b_3**2 - 4 * a_3 * c_3
                    if d_3 < 0:
                        print("Sensor 3: This equation has no real solution")
                        x3_1 = x3_2 = 0
                    elif d_3 == 0:
                        x3_1 = x3_2 = -b_3 / (2 * a_3)
                        print("Sensor 3: This equation has one solution: x3 =", x3_1)

                    else:
                        x3_1 = (-b_3 + math.sqrt(d_3)) / (2 * a_3)
                        x3_2 = (-b_3 - math.sqrt(d_3)) / (2 * a_3)
                        print("Sensor 3: This equation has two solutions: x3_1 =", x3_1, "or x3_2 =", x3_2)

# # -------------------------------------------------------------------------------------------------------------------------------
#                   # Calculate coefficients for Sensor 4
                    a_4 = M1
                    b_4 = N1 - ((2 * L0_4 * Alpha) / gtof4)
                    c_4 = P1 + ((2 * L0_4 * (Alpha * T0 - 1)) / gtof4)
                    # Solve quadratic equation for Sensor 4
                    d_4 = b_4**2 - 4 * a_4 * c_4
                    if d_4 < 0:
                        print("Sensor 4: This equation has no real solution")
                        x4_1 = x4_2 = 0
                    elif d_4 == 0:
                        x4_1 = x4_2 = -b_4 / (2 * a_4)
                        print("Sensor 4: This equation has one solution: x4 =", x4_1)
                    else:
                        x4_1 = (-b_4 + math.sqrt(d_4)) / (2 * a_4)
                        x4_2 = (-b_4 - math.sqrt(d_4)) / (2 * a_4)
                        print("Sensor 4: This equation has two solutions: x4_1 =", x4_1, "or x4_2 =", x4_2)                                         
                    # Predict using the trained models
                    # try:
                    #     P1_Vel1, P1_Temp1 = predict_temperature(gtof1, "wg1_T1", L1_value=L0_1, xscaler_loc=s1_xscaler_loc, yscaler_loc=s1_yscaler_loc, encoder_loc=s1_encoder_loc, model_loc=s1_model_loc)
                    #     P1_Vel2, P1_Temp2 = predict_temperature(gtof2, "wg1_T1", L1_value=L0_2, xscaler_loc=s2_xscaler_loc, yscaler_loc=s2_yscaler_loc, encoder_loc=s2_encoder_loc, model_loc=s2_model_loc)
                    #     P2_Vel1, P2_Temp1 = predict_temperature(gtof1, "wg1_T2", L1_value=L0_1, xscaler_loc=s1_xscaler_loc, yscaler_loc=s1_yscaler_loc, encoder_loc=s1_encoder_loc, model_loc=s1_model_loc)
                    #     P2_Vel2, P2_Temp2 = predict_temperature(gtof2, "wg1_T2", L1_value=L0_2, xscaler_loc=s2_xscaler_loc, yscaler_loc=s2_yscaler_loc, encoder_loc=s2_encoder_loc, model_loc=s2_model_loc)
                    #     P3_Vel1, P3_Temp1 = predict_temperature(gtof1, "wg1_T3", L1_value=L0_1, xscaler_loc=s1_xscaler_loc, yscaler_loc=s1_yscaler_loc, encoder_loc=s1_encoder_loc, model_loc=s1_model_loc)
                    #     P3_Vel2, P3_Temp2 = predict_temperature(gtof2, "wg1_T3", L1_value=L0_2, xscaler_loc=s2_xscaler_loc, yscaler_loc=s2_yscaler_loc, encoder_loc=s2_encoder_loc, model_loc=s2_model_loc)
                    #     P4_Vel1, P4_Temp1 = predict_temperature(gtof1, "wg1_T4", L1_value=L0_1, xscaler_loc=s1_xscaler_loc, yscaler_loc=s1_yscaler_loc, encoder_loc=s1_encoder_loc, model_loc=s1_model_loc)
                    #     P4_Vel2, P4_Temp2 = predict_temperature(gtof2, "wg1_T4", L1_value=L0_2, xscaler_loc=s2_xscaler_loc, yscaler_loc=s2_yscaler_loc, encoder_loc=s2_encoder_loc, model_loc=s2_model_loc)

                    # except Exception as e:
                    #     print("Prediction error:", e)
                    #     P1_Vel1 = P1_Temp1 = P1_Vel2 = P1_Temp2 = 0
                    #     P2_Vel1 = P2_Temp1 = P2_Vel2 = P2_Temp2 = 0
                    #     P3_Vel1 = P3_Temp1 = P3_Vel2 = P3_Temp2 = 0
                    #     P4_Vel1 = P4_Temp1 = P4_Vel2 = P4_Temp2 = 0
        
                    print("Ascan Number:", i)

                    overall_peak = [int(interpolatedIndexes[j]) for j in range(len(interpolatedIndexes))]
                    print(overall_peak)

                    c_time2 = os.path.getmtime(next_file)  # Getting timestamp values
                    dt_object2 = datetime.fromtimestamp(c_time2) # Converting timestamp values to datetime object

                    d2 = dt_object2.strftime("%Y-%m-%d %H:%M:%S")

                    # Gather values for watchdog
                    gtofs = [gtof1, gtof2, gtof3, gtof4]
                    amplitudes = [P_Amp1, P_Amp2, P_Amp3, P_Amp4, P_Amp5]
                    gate_shifts = [
                        sen_peaks1['peak1'].array[-1] if len(sen_peaks1) > 0 else 0,
                        sen_peaks1['peak2'].array[-1] if len(sen_peaks1) > 0 else 0,
                        sen_peaks1['peak3'].array[-1] if len(sen_peaks1) > 0 else 0,
                        sen_peaks1['peak4'].array[-1] if len(sen_peaks1) > 0 else 0,
                        sen_peaks1['peak5'].array[-1] if len(sen_peaks1) > 0 else 0,
                    ]
                    temperatures = [x1_2, x2_2, x3_2, x4_2]
                    
                    is_healthy = watchdog.check(gtofs, amplitudes, gate_shifts, temperatures)
                    
                    if not is_healthy:
                        # ─── AGENT TAKES CONTROL ───
                        print(f"[WATCHDOG] ANOMALY on file 1({i}).csv: {watchdog.anomaly_reason}")
                        
                        # Get the raw waveform for this file
                        raw_waveform = data1[3:]['average(A)'].replace('∞', 0).replace('-∞', 0)
                        raw_waveform = raw_waveform.to_numpy(dtype=np.float64).ravel()
                        
                        current_peaks = [
                            Start_P11 + max_index11,
                            Start_P12 + max_index12,
                            Start_P13 + max_index13,
                            Start_P14 + max_index14,
                            Start_P15 + max_index15,
                        ]
                        
                        result = agent_reselect(
                            waveform=raw_waveform,
                            current_peaks=current_peaks,
                            anomaly_reason=watchdog.anomaly_reason,
                            sample_freq_mhz=samplefreq_in_MHz,
                            gauge_lengths_um=gauge_lengths,
                            gate=gate,
                            db_path="Tof_data.db",
                        )
                        
                        # Reset all gate windows from agent's new peaks
                        Start_P11, End_P11 = result["new_gates"][0]
                        Start_P12, End_P12 = result["new_gates"][1]
                        Start_P13, End_P13 = result["new_gates"][2]
                        Start_P14, End_P14 = result["new_gates"][3]
                        Start_P15, End_P15 = result["new_gates"][4]
                        
                        # Clear the gate tracking history (fresh start)
                        sen_peaks = pd.DataFrame(columns=['Ascan File No.', 'peak1', 'peak2', 'peak3', 'peak4', 'peak5', 'peak6'])
                        sen_peaks1 = pd.DataFrame(columns=['Ascan File No.', 'peak1', 'peak2', 'peak3', 'peak4', 'peak5', 'peak6'])
                        
                        # Skip writing this bad reading to DB — go to next file
                        i += 1
                        plt.clf()
                        continue  # restart the while loop with new gates

                    TOF_df = pd.DataFrame({
                        'Ascan File No.': i,
                        'Creation_Time': d2,
                        'tor1': TOR1, 'Gtor1': GG1,
                        'tor2': TOR2, 'Gtor2': GG2,
                        'tor3': TOR3, 'Gtor3': GG3,
                        'tor4': TOR4, 'Gtor4': GG4,
                        'tor5': TOR5, 'Gtor5': GG5,
                        'Tof1': TOF_1, 'Tof2': TOF_2, 'Tof3': TOF_3, 'Tof4': TOF_4,
                        'Gtof1': gtof1, 'Gtof2': gtof2, 'Gtof3': gtof3, 'Gtof4': gtof4,
                        'Amp1': P_Amp1, 'Amp2': P_Amp2, 'Amp3': P_Amp3, 'Amp4': P_Amp4, 'Amp5': P_Amp5,
                        'S1': x1_2, 'S2': x2_2,'S3': x3_2, 'S4': x4_2
                    }, index=[0])
                    
                    # model_temp = pd.DataFrame({'Ascan File No.': i, 'Creation_Time': d2,'P1_Temp1': P1_Temp1, 'P1_Temp2': P1_Temp2,'P2_Temp1': P2_Temp1,
                    #                             'P2_Temp2': P2_Temp2,'P3_Temp1': P3_Temp1, 'P3_Temp2': P3_Temp2,'P4_Temp1': P4_Temp1, 'P4_Temp2': P4_Temp2
                    #                            }, index=[0])
                    
                   #################################################################################################################################

                    sen_peaks = pd.concat([sen_peaks, pd.DataFrame({'Ascan File No.': i, 'peak1': (Start_P11 + max_index11), 'peak2': (Start_P12 + max_index12),
                                                                     'peak3': (Start_P13 + max_index13),'peak4': (Start_P14 + max_index14),'peak5': (Start_P15 + max_index15)
                                                                    }, index=[0])],  ignore_index=True)
                    
                    if len(sen_peaks) > 10:
                        sen_peaks = sen_peaks.tail(5)
                    
                    ######################################

                    sen_peaks1 = sen_peaks.iloc[:,1:].diff().fillna(0).astype(float)
                    Start_P11 = int(Start_P11 + sen_peaks1['peak1'].array[-1])
                    End_P11 = int(End_P11 + sen_peaks1['peak1'].array[-1])
                    Start_P12 = int(Start_P12 + sen_peaks1['peak2'].array[-1])
                    End_P12 = int(End_P12 + sen_peaks1['peak2'].array[-1])
                    Start_P13 = int(Start_P13 + sen_peaks1['peak3'].array[-1])
                    End_P13 = int(End_P13 + sen_peaks1['peak3'].array[-1])
                    Start_P14 = int(Start_P14 + sen_peaks1['peak4'].array[-1])
                    End_P14 = int(End_P14 + sen_peaks1['peak4'].array[-1])
                    Start_P15 = int(Start_P15 + sen_peaks1['peak5'].array[-1])
                    End_P15 = int(End_P15 + sen_peaks1['peak5'].array[-1])

                    
                    ########################################################
    
      
                    TOF_df.to_sql('Tof_data',con,if_exists='append',index=False)
                    # model_temp.to_sql('Model_Temp',con,if_exists='append',index=False)
                    
                    #####################################
                    query = 'SELECT "Ascan File No.",Gtof1,Gtof2,Gtof3,Gtof4,S1,S2,S3,S4 FROM Tof_data'
                    plot_df = pd.read_sql(query,con)
                    
                    #####################################
                    
                    #####################################

                    present = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # Plot
                    
                    font1={'color': 'black','size': 12,'weight': 'bold','style':'normal'}
  
                    plt.subplot(3,1,1)
                    plt.plot(a, label="Signal")
                    plt.scatter(overall_peak, a[overall_peak], color='orange', marker='x', label='Peaks')
                    # plt.ylim(-2,2)
                    # plt.xlim(0,80000)
                
                    
                    ##############################################

                    # plt.axvline(x=Start_P11, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=End_P11, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=Start_P12, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=End_P12, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=Start_P13, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=End_P13, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=Start_P14, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=End_P14, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=Start_P15, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=End_P15, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=Start_P16, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=End_P16, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=Start_P17, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=End_P17, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=Start_P18, ymin=0.1, ymax=0.9,color='r',linestyle='--')
                    # plt.axvline(x=End_P18, ymin=0.1, ymax=0.9,color='r',linestyle='--')

                    ########################################################
                    ########################################################
            
                    
                    plt.xlabel("Sample Index",fontweight='bold')
                    plt.ylabel("Amplitude",fontweight='bold')
                    plt.title(f"Rio_Tinto_New_Wg_Cal_Trial4 || File 1({i}).csv & Recorded on " + str(d2),fontdict=font1, bbox=dict(facecolor='yellow') )
                    plt.grid(True)


                    plt.subplot(3,4,5)
                    plt.scatter(plot_df['Ascan File No.'], plot_df['Gtof1'], label="Gtof1",color='red',marker = 'x')
                    plt.xlabel("Index",fontweight='bold')
                    plt.ylabel("Gtof",fontweight='bold')
                    plt.title(f"Gtof1: {round(gtof1,4)}",fontdict=font1, bbox=dict(facecolor='yellow'))
                    
                    plt.subplot(3,4,6)
                    plt.scatter(plot_df['Ascan File No.'], plot_df['Gtof2'], label="Gtof2",color='pink',marker = 'x')
                    plt.xlabel("Index",fontweight='bold')
                    plt.ylabel("Gtof",fontweight='bold')
                    plt.title(f"Gtof2: {round(gtof2,4)}",fontdict=font1, bbox=dict(facecolor='yellow'))

                    plt.subplot(3,4,7)
                    plt.scatter(plot_df['Ascan File No.'], plot_df['Gtof3'], label="Gtof3",color='purple',marker = 'x')
                    plt.xlabel("Index",fontweight='bold')
                    plt.ylabel("Gtof",fontweight='bold')
                    plt.title(f"Gtof3: {round(gtof3,4)}",fontdict=font1, bbox=dict(facecolor='yellow'))

                    plt.subplot(3,4,8)
                    plt.scatter(plot_df['Ascan File No.'], plot_df['Gtof4'], label="Gtof4",color='brown',marker = 'x')
                    plt.xlabel("Index",fontweight='bold')
                    plt.ylabel("Gtof",fontweight='bold')
                    plt.title(f"Gtof4: {round(gtof4,4)}",fontdict=font1, bbox=dict(facecolor='yellow'))
                    
                    plt.subplot(3,4,9)
                    plt.scatter(plot_df['Ascan File No.'], plot_df['S1'], label="S1",color='blue',marker = 'x')
                    plt.xlabel("Index",fontweight='bold')
                    plt.ylabel("Temperature",fontweight='bold')
                    plt.title(f"S1: {round(x1_2,4)}",fontdict=font1, bbox=dict(facecolor='yellow'))
                    
                    plt.subplot(3,4,10)
                    plt.scatter(plot_df['Ascan File No.'], plot_df['S2'], label="S2",color='black',marker = 'x')
                    plt.xlabel("Index",fontweight='bold')
                    plt.ylabel("Temperature",fontweight='bold')
                    plt.title(f"S2: {round(x2_2,4)}",fontdict=font1, bbox=dict(facecolor='yellow'))

                    plt.subplot(3,4,11)
                    plt.scatter(plot_df['Ascan File No.'], plot_df['S3'], label="S3",color='cyan',marker = 'x')
                    plt.xlabel("Index",fontweight='bold')
                    plt.ylabel("Temperature",fontweight='bold')
                    plt.title(f"S3: {round(x3_2,4)}",fontdict=font1, bbox=dict(facecolor='yellow'))

                    plt.subplot(3,4,12)
                    plt.scatter(plot_df['Ascan File No.'], plot_df['S4'], label="S4",color='orange',marker = 'x')
                    plt.xlabel("Index",fontweight='bold')
                    plt.ylabel("Temperature",fontweight='bold')
                    plt.title(f"S4: {round(x4_2,4)}",fontdict=font1, bbox=dict(facecolor='yellow'))
                    
                    # plt.subplot(3,3,8)
                    # plt.scatter(plot_df['Ascan File No.'], plot_df['Gtof5'], label="Gtof5",color='red',marker = 'x')
                    # plt.xlabel("Index",fontweight='bold')
                    # plt.ylabel("Gtof5",fontweight='bold')
                    # plt.title(f"Gtof5: {round(gtof5,4)}",fontdict=font1, bbox=dict(facecolor='yellow'))
                    
                    # plt.subplot(3,3,9)
                    # plt.scatter(plot_df['Ascan File No.'], plot_df['Gtof6'], label="Gtof6",color='red',marker = 'x')
                    # plt.xlabel("Index",fontweight='bold')
                    # plt.ylabel("Gtof6",fontweight='bold')
                    # plt.title(f"Gtof6: {round(gtof6,4)}",fontdict=font1, bbox=dict(facecolor='yellow'))
                    

                    #  ########################################
                    #######################################################
                    
                #                    
                    
                    plt.tight_layout()  # Adjust layout to prevent overlap
                    writers.grab_frame()
                    print("Frame grabbed")
                    plt.pause(0.01)
    
                    plt.clf()
                    
                    i+=1
                    plot_df = pd.DataFrame() 
                    
             
                except Exception as e:
                    print(e)
                

except KeyboardInterrupt:
    print('Keyboard Interrupt')
