# -*- coding: utf-8 -*-
"""
Created on Tue Nov 30 16:36:55 2021

@author: spenc
"""
#%%
import mne
import numpy as np
import matplotlib.pyplot as plt
from filter_ssvep_data import make_bandpass_filter
from filter_ssvep_data import filter_data
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split

def load_data(subject):
    fif_file=mne.io.read_raw_fif(f'P{subject}-raw.fif', preload=True)
    raw_eeg_data = fif_file.get_data()[0:64, :]
    channel_names = fif_file.ch_names[0:64]
    eeg_times = fif_file.times
    fs = fif_file.info['sfreq']
    return fif_file, raw_eeg_data, eeg_times, np.array(channel_names), fs
    

fif_file, raw_eeg_data, eeg_times, channel_names, fs = load_data('13')

start_time = 0
end_time = 5


filter_coefficients = make_bandpass_filter(40, 60, 1000, fs, filter_type = 'hann')

filtered_data = filter_data(raw_eeg_data, filter_coefficients)

def get_eeg_epochs(fif_file, raw_eeg_data, start_time, end_time, fs):
    eeg_epochs = np.array([])
    all_trials = mne.find_events(fif_file)
    target_events = all_trials[np.logical_not(np.logical_and(all_trials[:,2] > 20, all_trials[:,2] > 999))]
    
    
    event_stimulus_ids = []
    for event_index in range(len(target_events)):
        stimulus_id = target_events[event_index, 2]//10
        event_stimulus_ids.append(stimulus_id)
        
    event_start_times = target_events[:, 0]
    for event_start_time in event_start_times:
        start_epoch = int(event_start_time) - int(start_time*fs)
        end_epoch = int(int(event_start_time) + (end_time*fs))
        epoch_data = raw_eeg_data[:, start_epoch:end_epoch]
        eeg_epochs = np.append(eeg_epochs, epoch_data)
    eeg_epochs = np.reshape(eeg_epochs, [len(target_events), np.size(raw_eeg_data, axis=0), int(end_time*fs)])
    epoch_times = np.arange(0, np.size(eeg_epochs, axis=2))
    return eeg_epochs, epoch_times, target_events, all_trials, event_stimulus_ids

eeg_epochs, epoch_times, target_events, all_trials, event_stimulus_ids = get_eeg_epochs(fif_file, filtered_data, start_time, end_time, fs)






def get_tempo_labels(event_stimulus_ids):
    tempo_labels=[]
    for stimulus_id in event_stimulus_ids:
        if stimulus_id == 1 or stimulus_id==11:
            tempo=212
        elif stimulus_id == 2 or stimulus_id==12:
            tempo=189
        elif stimulus_id == 3 or stimulus_id==13:
            tempo=200
        elif stimulus_id == 4 or stimulus_id==14:
            tempo=160
        elif stimulus_id == 21:
            tempo = 178
        elif stimulus_id == 22:
            tempo = 166
        elif stimulus_id == 23:
            tempo = 104
        elif stimulus_id == 24:
            tempo = 140
        
        tempo_labels.append(tempo)
    return np.array(tempo_labels)

tempo_labels = get_tempo_labels(event_stimulus_ids)


def get_truth_labels(tempo_labels):
    is_trial_greater_than_170bpm = [tempo_labels[:] >= 170]
    return is_trial_greater_than_170bpm[0]

is_trial_greater_than_170bpm=get_truth_labels(tempo_labels)

def get_frequency_spectrum(eeg_epochs, fs):
    eeg_epochs_fft = np.fft.rfft(eeg_epochs)
    fft_frequencies = np.fft.rfftfreq(np.size(eeg_epochs, axis=2), d=1/fs) 
    
    return eeg_epochs_fft, fft_frequencies



eeg_epochs_fft, fft_frequencies = get_frequency_spectrum(eeg_epochs, fs)


channels_to_plot = ['TP7']

def plot_power_spectrum(eeg_epochs_fft, fft_frequencies, is_trial_greater_than_170bpm, channels_to_plot, channels):
    '''
    

    Parameters
    ----------
    eeg_epochs_fft : Array of complex128
        3-D array holding epoched data in the frequency domain for each trial.
    fft_frequencies : Array of float64
        Array containing the frequency corresponding to each column of the Fourier transform data.
    is_trial_15Hz : 1-D boolean array 
        Boolean array representing trials in which flashing at 15 Hz occurred.
    channels_to_plot : list 
        list of channels we wish to plot the raw data for.
    channels : Array of str128
        List of channel names from original dataset.

    Returns
    -------
    None.

    '''
    mean_channel_power = np.mean(abs(eeg_epochs_fft), axis=2)**2
    eeg_trials_g170bpm = eeg_epochs_fft[is_trial_greater_than_170bpm]
    eeg_trials_l170bpm = eeg_epochs_fft[~is_trial_greater_than_170bpm]
    
    # Calculate mean power spectra
    mean_power_spectrum_g170 = np.mean(abs(eeg_trials_g170bpm), axis=0)**2
    mean_power_spectrum_l170 = np.mean(abs(eeg_trials_l170bpm), axis=0)**2
    
    # Normalize spectrum
    mean_power_spectrum_g170_norm = mean_power_spectrum_g170/mean_power_spectrum_g170.max(axis=1, keepdims=True)
    mean_power_spectrum_l170_norm = mean_power_spectrum_l170/mean_power_spectrum_l170.max(axis=1, keepdims=True)

    # Convert to decibels
    power_in_db_g170 = 10*np.log10(mean_power_spectrum_g170_norm)
    power_in_db_l170 = 10*np.log10(mean_power_spectrum_l170_norm)

    # Plot mean power spectrum of 12 and 15 Hz trials
    for channel_index, channel in enumerate(channels_to_plot):
        index_to_plot = np.where(channels==channel)[0][0]
        ax1=plt.subplot(len(channels_to_plot), 1, channel_index+1)
        plt.plot(fft_frequencies,power_in_db_g170[index_to_plot], label='> 170 BPM', color='red')
        plt.plot(fft_frequencies,power_in_db_l170[index_to_plot], label='< 170 BPM', color='green')
        plt.legend()
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Power (dB)')
        plt.tight_layout()

        plt.grid()

    
    return mean_channel_power
power = plot_power_spectrum(eeg_epochs_fft, fft_frequencies, is_trial_greater_than_170bpm, channels_to_plot, channel_names)



def perform_ICA(raw_fif_file):
    ica = mne.preprocessing.ICA(n_components=20, random_state=97, max_iter=800)
    ica.fit(raw_fif_file)






def extract_eeg_features(eeg_epochs):
    mean_eeg = np.mean(eeg_epochs, axis=2)
    rms_eeg = np.sqrt(np.mean(eeg_epochs**2, axis=2))
    std_eeg = np.std(eeg_epochs, axis=2)

    return mean_eeg, rms_eeg, std_eeg

mean_eeg, rms_eeg, std_eeg = extract_eeg_features(eeg_epochs)

plt.plot(epoch_times, np.mean(eeg_epochs, axis=0))

X_train, X_test, y_train, y_test = train_test_split(power, is_trial_greater_than_170bpm*1, test_size=.15)
clf = SVC(C=.1, gamma=10, class_weight={0:1, 1:1})
clf.fit(X_train, y_train)
y_pred = clf.predict(X_test)


# %%
