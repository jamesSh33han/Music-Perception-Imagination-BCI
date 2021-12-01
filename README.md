# BME-296-BCI-Final-Project


Here we are using a public dataset of EEG recordings taken during music perception and imagination. The data was acquired during an ongoing study that so far comprised 10 subjects listening to and imagining 12 short music fragments (each 7-16 seconds long) taken from well-known musical pieces. The stimuli were selected from different genres and capture several musical dimensions such as tempo and the presence of lyrics. The dataset is intended to enable music information retrieval researchers to easily test and adapt their existing approaches for music analysis like fingerprinting, beat tracking or tempo estimation on this new kind of data. The 10 subjects are currently denoted as P01, P04, PO5, PO6, PO7, PO9, PO11, PO12, PO13, and PO14. This dataset is a result of ongoing joint work between the Owen Lab and the Music and Neuroscience Lab at the Brain and Mind Institute of the University of Western Ontario. Information on loading the data in Python is below:

Link to download data by subject: http://bmi.ssc.uwo.ca/OpenMIIR-RawEEG_v1/

Notes pertaining to data:

- Loaded in MNE’s .fif format
- Raw EEG, EEG sample times (in seconds), channel names, and the sampling frequency can be extracted from the file
- Raw EEG of size (channels, time points) in our case (64, 2478166)
- EEG sample times of length 2478166
- 64 channels, channel names are a list of channels
- Sampling frequency of 512 Hz


Epoching Data:
- Use MNE’s built in find_events() and Epochs() functions to epoch the data into the 240 trials 

Code to load and handle data:

```
import mne
```

```
fif_file=mne.io.read_raw_fif(f'{subject}-raw.fif', preload=True)
```

```
def load_data(subject):
    fif_file=mne.io.read_raw_fif(f'{subject}-raw.fif', preload=True)
    raw_eeg_data = fif_file.get_data()
    channel_names = fif_file.ch_names[0:64]
    eeg_times = fif_file.times
    fs = fif_file.info['sfreq']
    return fif_file, raw_eeg_data, eeg_times, channel_names, fs
    

fif_file, raw_eeg_data, eeg_times, channel_names = load_data('P01')
```





