# -*- coding: utf-8 -*-
"""
Created on Tue Nov 30 16:36:55 2021

Project3.py

File that defines functions load_data, get_eeg_epochs, get_truth_event_labels, plot_power_spectrum, perform_ICA, 
plot_component_variance, make_prediction, evaluate_predictions, and test_all_component_thresholds.

These functions load in a specified subjects raw EEG data file from the OPENMIIR dataset, epochs the EEG data into
target/nontarget epochs, defines truth event labels from the epoched data (target = participant was listeing to music, 
nontarget = participant imagined music), computes ICA on the pre-processed EEG data, plots component maps and source activity
from ICA results, generates a list of predicted Target/Nontarget labels that are classified by using the variance of source 
activations from a given component as features, compare predicted labels to truth labels to generate a confusion matrix, and
compare classification accuracy across an array of different thresholds. Also calculates ITR given an accuracy and trial duration

@author: spenc, JJ
"""
#%% Import Statements
import mne
import numpy as np
import matplotlib.pyplot as plt
from mne.preprocessing import ICA
import math
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
# Define figure size
plt.rcParams["figure.figsize"] = (14,8)

#%% Loading in raw data, Band-pass filtering, and re-referencing
def load_data(subject):
    '''
    Function to load in a specified subjects .fif data file, Band-pass filter the raw EEG data between 1 - 30Hz, and
    re-reference the data to the average across electrodes.

    Parameters
    ----------
    subject : string of subject number (two digits)
        String denoting which subject we are analyzing.

    Returns
    -------
    fif_file : Raw MNE FIF file
        FIF file with MNE built in functions - all data can be extracted.
    raw_eeg_data : Array of size (channels, samples) - samples depend on which subject is read
        Array of floats containing the eeg recording data taken at each time point (across all
        trials and condiditons) for the one subject.
    eeg_times : Array of time points eeg samples were taken
        1-D array of times (in seconds) of the time points each eeg sample was taken at.
    channel_names: Array of channel names (each is string)
        Array of eeg channel names.
    fs : float
        smapling frquency of 512 Hz.

    '''

    fif_file=mne.io.read_raw_fif(f'data/P{subject}-raw.fif', preload=True)
    
    # pre-processing data before extraction
    print('Band-pass filtering between 1 - 30 Hz...')
    fif_file.filter(1,30)
    print('Rereferencing the raw data to the average across electrodes...')
    fif_file.set_eeg_reference(ref_channels='average')
    
    # extracting data
    raw_eeg_data = fif_file.get_data()[0:64, :]
    channel_names = fif_file.ch_names[0:64]
    eeg_times = fif_file.times
    fs = fif_file.info['sfreq']
    channel_names = np.array(channel_names)
    return fif_file, raw_eeg_data, eeg_times, channel_names, fs
    


#%% Epoching the data
def get_eeg_epochs(fif_file, raw_eeg_data, start_time, end_time, fs):
    '''
    Function to epoch the EEG raw data into target/nontarget epochs. 

    Parameters
    ----------
    fif_file : Raw MNE FIF file
        FIF file with MNE built in functions - all data can be extracted.
    raw_eeg_data : Array of size (channels, samples) - samples depend on which subject is read
        Array of floats containing the eeg recording data taken at each time point (across all
        trials and condiditons) for the one subject.
    start_time : float
        start time relative to event start.
    end_time : float
        end time relative to event start.
    fs : float
        smapling frquency of 512 Hz.

    Returns
    -------
    eeg_epochs : 3-D Array of size (trials, channels, time points)
        3-D array contianing epoched eeg data into the trials seen in the experiment.
    epoch_times : 1-D array of length epoch time points
        Array of times using epoch time points.
    target_events : array of size (target_events, (event onset, post-experiment feedback, stimulus/condiiton id))
        array containing the information on the target events (where the participant was listeing to music).
    all_trials : array of size (all trials, (event onset, post-experiment feedback, stimulus/condiiton id))
        array containing the information on all events.

    '''
    eeg_epochs = np.array([])
    
    # finding all trials present in experiment
    all_trials = mne.find_events(fif_file)
    # only using event trials (when music was perceived or imagined) - any event id under 1000 is one of the event trials
    all_trials = all_trials[all_trials[:, 2] <1000]

    # get all event start times    
    event_start_times = all_trials[:, 0]
    # epoch the data based on user entered end time and start time starting at onset of trial
    for event_start_time in event_start_times:
        start_epoch = int(event_start_time) - int(start_time*fs)
        end_epoch = int(int(event_start_time) + (end_time*fs))
        epoch_data = raw_eeg_data[:, start_epoch:end_epoch]
        eeg_epochs = np.append(eeg_epochs, epoch_data)
    eeg_epochs = np.reshape(eeg_epochs, [len(all_trials), np.size(raw_eeg_data, axis=0), int(end_time*fs)])
    epoch_times = np.arange(0, np.size(eeg_epochs, axis=2))
    return eeg_epochs, epoch_times, all_trials

#%% Setting Event Truth Labels
def get_event_truth_labels(all_trials):
    '''
    Function to go through the data from every event and label each event as a target event (true) or a nontarget event (false)

    Parameters
    ----------
    all_trials : array of size (all trials, (event onset, post-experiment feedback, stimulus/condiiton id))
        array containing the information on all events (both perceived and imagined trials).

    Returns
    -------
    is_target_event: boolean array
        boolean array containing labels denoting weather trial contained a perceived music (target) event or not.

    '''
    # initialize array
    is_target_event = np.array([])
    # for each trial that occured, label if trial was a target (perceived music) event or not
    for trial_index in range(len(all_trials)):
        # decode event id and condition
        event_id = all_trials[trial_index, 2]
        condition = event_id % 10
        # if the condition 1 then it was perceived music, if not it was imagined
        if condition == 1:
            is_target_event = np.append(is_target_event,True)
        elif condition == 2 or condition==3 or condition == 4:
            is_target_event = np.append(is_target_event,False)
        else:
            pass
    is_target_event = np.array(is_target_event, dtype='bool')
    return is_target_event



#%% Running ICA and plotting component variance
def perform_ICA(raw_fif_file, channel_names, top_n_components):
    '''
    Function to preform ICA on the specified raw EEG data

    Parameters
    ----------
    fif_file : Raw MNE FIF file
        FIF file with MNE built in functions - all data can be extracted.
    channel_names: Array of channel names (each is string)
        Array of eeg channel names.
    top_n_components : int
        the number of top components the user wishes to plot.

    Returns
    -------
    ica : ICA Object of mne.preprocessing.ica module
        contains ICA data

    '''
    # use only the eeg channels for fitting ICA
    picks_eeg = mne.pick_types(raw_fif_file.info, meg=False, eeg=True, eog=False, stim=False, exclude='bads')[0:64]
    # calculate ICA components
    ica = mne.preprocessing.ICA(n_components=64, random_state=97, max_iter=800)
    # fit ICA 
    ica.fit(raw_fif_file, picks=picks_eeg, decim=3, reject=dict(mag=4e-12, grad=4000e-13))
    mixing_matrix = ica.mixing_matrix_
    # plot the components topo maps
    ica.plot_components(picks = np.arange(0,top_n_components))
    plt.savefig(f'figures/Top{top_n_components}ICA.png')

    return ica


def plot_component_variance(ica, components, eeg_epochs, is_target_event):
    '''
    Function to plot component variance from ICA results

    Parameters
    ----------
    ica : ICA Object of mne.preprocessing.ica module
        contains ICA data
    components : Array of int
        Number of components to plot
    eeg_epochs : 3-D Array of size (trials, channels, time points)
        3-D array contianing epoched eeg data into the trials seen in the experiment.
    is_target_event : 1-D boolean array 
        Boolean array representing trials the subject perceived music vs imagined music.

    Returns
    -------
    source_activations : Array of float
        Array representing source activation data from each independant component of size (trials, channels, time-course of activation)

    '''
    # calc mixing and unmixing matrices
    mixing_matrix = ica.mixing_matrix_
    unmixing_matrix = ica.unmixing_matrix_
    # calc source activations from epoched eeg data
    source_activations = np.matmul(unmixing_matrix, eeg_epochs)
    plt.figure('variance hists')
    # for each component, plot the histogram of variances over all trials
    for component in components:
        plt.subplot(2,5,component+1)
        # isolate one components source activity
        component_activation = source_activations[:, component, :]
        # calc varaince of source activity
        component_activation_variances = np.var(component_activation, axis = 1)
        # break into different trial types
        target_activation_vars = component_activation_variances[is_target_event]
        nontarget_activation_vars = component_activation_variances[~is_target_event]
        nontarget_activation_vars = np.delete(nontarget_activation_vars, 178)
        
        # plot each components variances broken up by trials in a subplot
        plt.hist([target_activation_vars, nontarget_activation_vars], label=['Perception', 'Imagination'])
        plt.xlabel('Variance')
        plt.ylabel('Count')
        plt.legend()
        plt.title(f'component {component} variance')
    plt.tight_layout()
    plt.savefig(f'figures/TopComponentVariances.png')
    return source_activations

#%% Classification of Target/Nontarget events
def make_prediction(source_activations, component, is_target_event, threshold):
    '''
    Function to generate a list of predicted Target/Nontarget labels that are classified by using the variance of 
    source activations from a given component as features. The component used to make predictions was selected by analyzing
    the component maps and source activy generated from ICA and finding the component that most closely matches the auditory
    N1 and P1 signals.

    Parameters
    ----------
    source_activations : Array of float
        Array representing source activation data from each independant component of size (trials, channels, time-course of activation)
    component : int
        Component that most closely matches the auditory N1 and P1. This component's source activation variance will be used to generate predictions'
    is_target_event : 1-D boolean array 
        Boolean array representing trials the subject perceived music vs imagined music.
    threshold : float
        Number to compare component activation variances to in order to determine predicted labels

    Returns
    -------
    predicted_labels : list
        Contains calculated prediction values. If it was predicted a subject was listening to music,  predicted_labels[i] = 1, and
        if it was predicted a subject was imagining the music,  predicted_labels[i] = 0

    '''
    component_activation = source_activations[:, component, :]
    component_activation_variances = np.var(component_activation, axis = 1)
    # for each trial, predict weather it is perceived or imagined based on component variance
    predicted_labels = [] 
    for variance in component_activation_variances:
        # if variance above threshold - perceived trial. Else imagined
        if variance >= threshold:
            predicted_labels.append(1)
            
        else:
            predicted_labels.append(0)
            
    return predicted_labels

def evaluate_predictions(predictions, truth_labels):
    '''
    Function to compare predicted labels to truth labels to generate a confusion matrix

    Parameters
    ----------
    predictions : List
        Contains calculated prediction values. If it was predicted a subject was listening to music, predicted_labels[i] = 1, 
        and if it was predicted a subject was imagining the music, predicted_labels[i] = 0
    truth_labels : Array of int
        Contains truth labels for whether a trial was a target (subject listening to music) or nontarget (subject imagining music)

    Returns
    -------
    accuracy : float
        Value to represent how accurately we classified target/nontarget labels. This value is the mean of how many times our 
        predicted label was equal to the truth label
    cm : Confusion Matrix
        Object to store classification results
    disp : Confusion Matrix
        Object to display classification results

    '''
    # calc accuracy based on predicted labels and truth labels
    accuracy = np.mean(predictions==truth_labels)
    # create confusion matrix
    cm = confusion_matrix(truth_labels, predictions)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm)
    return accuracy, cm, disp
    
def calculate_itr(accuracy, duration, truth_labels):
    '''
    Function that uses the given ITR formula to calculate ITR given an accuracy and trial duration

    Parameters
    ----------
    accuracy : float 
        Float representing the accuracy of our prediction as the proportion of correctly predicted trials divided by total number of trials.
    duration : float
        Float representing the time window we are using for epoching data.
    truth_labels : Array of length (trials)
        Array holding the truth labels for each trial. truth_labels[i] would indicate wheather trial i is of the lower or higher frequency.


    Returns
    -------
    itr_time : float
        Float which is the ITR in bits per second for the given accuracy and trial duration.

    '''
    # calculate the number of classes present in our data - it will be the number of unique truth labels
    n = len(np.unique(truth_labels))
    p = accuracy
    # use itr formula given, if accuracy = 1, ITR blows up, set equal to 1
    if p == 1: 
        itr_trial=1
    else:
        itr_trial = np.log2(n) + p*np.log2(p) + (1-p) * np.log2((1-p)/(n-1))
    itr_time = itr_trial*(1/duration)
    return itr_time   

def test_all_components_thresholds(components, source_activations, is_target_event):
    '''
    Function to create an array of potential thresholds based on each components range of source activation variances,
    and then test each potential threshold to determine the threshold that gives us the highest predicted accuracy

    Parameters
    ----------
   components : Array of int
        Number of components to test thresholds for
   source_activations : Array of float
        Array representing source activation data from each independant component of size (trials, channels, time-course of activation)
   is_target_event : 1-D boolean array 
        Boolean array representing trials the subject perceived music vs imagined music.

    Returns
    -------
    all_accuracies : Array of float
        Array of calculated accuracy values with varying threshold values for each component
    all_thresholds : Array of float
        contains range of 10 possible threshold values for each selected component (in this case 10 components)
    all_true_positives : Array of float
        Array of values for when our classifier accurately predicted the subject was actually hearing music

    '''
    all_accuracies = np.array([])
    all_thresholds = np.array([])
    all_true_positive_percentages = np.array([])
    components = components[::-1]
    # for each component and threshold pair, calculate the accuracy, and true positives of our classifer 
    for component in components:
        component_activation = source_activations[:, component, :]
        component_activation_variances = np.var(component_activation, axis = 1)
        # delete 238th variance, very large relatively, outlier
        component_activation_variances = np.delete(component_activation_variances, 238)
        # min and max threshold that would be viable on a certain component based on specific components variance values
        min_threshold = np.min(component_activation_variances)
        max_threshold = np.max(component_activation_variances)
        # creates an array of thresholds based on the components range of values
        thresholds = np.arange(min_threshold, max_threshold, (max_threshold-min_threshold)/10)
        all_thresholds = np.append(all_thresholds, thresholds)
        for threshold in thresholds:
            predicted_labels = make_prediction(source_activations, component, is_target_event, threshold)
            accuracy, cm, disp = evaluate_predictions(predicted_labels, is_target_event*1)
            all_accuracies = np.append(all_accuracies, accuracy)
            tp_percent = cm[1][1]/60
            all_true_positive_percentages = np.append(all_true_positive_percentages, tp_percent)
    all_accuracies = np.reshape(all_accuracies, (len(thresholds), len(components)))        
    all_thresholds = np.reshape(all_thresholds, (len(thresholds), len(components)))
    all_true_positive_percentages = np.reshape(all_true_positive_percentages, (len(thresholds), len(components)))
    
    # plot metrics for each component/threshold pair on pseudocolor subplots
    plt.subplot(1, 3, 1)
    plt.imshow(all_accuracies, extent = (components[-1], components[0], components[-1], components[0]))
    plt.colorbar(label = 'Accuracy (% Correct)', fraction=0.046, pad=0.04)
    plt.xlabel('Threshold Index')
    plt.ylabel('Component')
    plt.title('All Component/Threshold Accuracies')

    plt.subplot(1, 3, 2)
    plt.imshow(all_true_positive_percentages, extent = (components[-1], components[0], components[-1], components[0]))
    plt.colorbar(label = 'TP %', fraction=0.046, pad=0.04)
    plt.xlabel('Threshold Index')
    plt.ylabel('Component')
    plt.title('All Component/Threshold True Positives')
   
    plt.subplot(1, 3, 3)
    plt.imshow(np.mean(np.array([all_accuracies, all_true_positive_percentages]), axis=0 ), extent = (components[-1], components[0], components[-1], components[0]))
    plt.colorbar(label = 'Average of TP% and Accuracy', fraction=0.046, pad=0.04)
    plt.xlabel('Threshold Index')
    plt.ylabel('Component')
    plt.title('Average of All Component/Threshold Accuracies and True Positives')
    
    plt.tight_layout()
    plt.savefig(f'figures/AllMetrics.png')

    return all_accuracies, all_thresholds, all_true_positive_percentages
    
