import os
import glob
import re
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import welch

'''
Development mode for testing
To do: add code to handle q-factor calculations
'''

class PSDAnalyzer:
    def __init__(self):
        pass  # set with function calls

    def compute_psd(self, file_path, nperseg=2**22):
        '''Compute and save PSD for a single file and return frequency, pxx, pyy'''
        output_file_name = os.path.join(os.path.dirname(file_path), os.path.splitext(os.path.basename(file_path))[0] + "_psd.npz")


        data = np.load(file_path)
        x = data['channel_1']
        y = data['channel_2']
        s = data['channel_3']
        t = data['t']

        sam_freq = 1 / (t[1] - t[0])
        freq, pxx = welch(x, fs=sam_freq, nperseg=nperseg)
        _, pyy = welch(y, fs=sam_freq, nperseg=nperseg)

        print(f'Processed file: {file_path}')
        print(f'Mean voltage of sum channel: {np.mean(s)}')

        # Save the results
        np.savez(output_file_name, freq=freq, pxx_avg=pxx, pyy_avg=pyy)
        print(f"PSD saved to: {output_file_name}")

    def compute_avg_psd(self, folder_path, output_dir='avg_psd', output_suffix='_averaged_psd', nperseg=2**22):
        '''Compute and save the averaged PSD from already computed singular PSD files.'''
        psd_files = glob.glob(f'{folder_path}/*_psd.npz')

        if not files:
            raise ValueError(f"No npz files found in {folder_path}")

        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        folder_name = os.path.basename(os.path.normpath(folder_path))
        output_file_name = os.path.join(output_dir, f'{folder_name}{output_suffix}.npz')

        pxx_list = []
        pyy_list = []
        sam_freq = None

        # Load first PSD file to get frequency bins
        first_file = np.load(psd_files[0])
        freq = first_file["freq"]  # Use the first PSD file's frequency bins
        first_file.close()

        for file in psd_files:
            data = np.load(file)
            pxx_list.append(data["pxx_avg"])
            pyy_list.append(data["pyy_avg"])
            data.close()

        # Convert lists to arrays and compute mean across all files
        pxx_avg = np.mean(np.array(pxx_list), axis=0)
        pyy_avg = np.mean(np.array(pyy_list), axis=0)

        # Save the results
        np.savez(output_file_name, freq=freq, pxx_avg=pxx_avg, pyy_avg=pyy_avg)
        print(f"Averaged PSD saved to: {output_file_name}")

    def compute_avg_psd_2(self, folder_path, output_dir='avg_psd', output_suffix='_averaged_psd', nperseg=2**22):
        '''Compute and save the averaged PSD from all files in the specified folder using list-based averaging if 
        you haven't computed singular psds to start.'''
        files = glob.glob(f'{folder_path}/*.npz')

        if not files:
            raise ValueError(f"No npz files found in {folder_path}")

        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        folder_name = os.path.basename(os.path.normpath(folder_path))
        output_file_name = os.path.join(output_dir, f'{folder_name}{output_suffix}.npz')

        pxx_list = []
        pyy_list = []
        sam_freq = None

        for file in files:
            freq, pxx, pyy = self.compute_psd(file, nperseg=nperseg)
            pxx_list.append(pxx)
            pyy_list.append(pyy)

        # Convert lists to arrays and compute mean across all files
        pxx_avg = np.mean(np.array(pxx_list), axis=0)
        pyy_avg = np.mean(np.array(pyy_list), axis=0)

        # Save the results
        np.savez(output_file_name, freq=freq, pxx_avg=pxx_avg, pyy_avg=pyy_avg)
        print(f"Averaged PSD saved to: {output_file_name}")

class PSDPlotter:
    def __init__(self, file_list):
        self.file_list = file_list

    def extract_pressure(self, file_name):
        # Extract pressure from the filename
        match = re.match(r'.*?(\d+_\d+)_mbar', file_name)
        return match.group(1).replace('_', '.') if match else 'Unknown'

    def extract_label(self, file_name, style='pressure'):
        '''
        Extract labels based on the given style.
        Options: 'pressure', 'sample'.
        '''
        if style == 'pressure':
            return f'Pressure: {self.extract_pressure(file_name)} mbar'
        elif style == 'sample':
            return 'No Sample' if 'no_sample' in file_name else 'Sample'
        else:
            return 'Unknown Label'

    def plot(self, label_style='pressure', include_x=False, title=None, xlim=None):
        '''
        Plot PSDs with specified label style.
        
        Args:
        - label_style: 'pressure', 'sample'
        - include_x: If True, include pxx_avg in the plot
        - title: Custom title for the plot
        - xlim: Tuple specifying the x-axis limits (e.g., (0, 100)) or None for no limits
        '''
        plt.figure(figsize=(10, 6))

        for file in self.file_list:
            data = np.load(file)
            freq = data['freq']
            pxx_avg = data['pxx_avg']
            pyy_avg = data['pyy_avg']

            label = self.extract_label(file, style=label_style)

            # Plot Y channel
            plt.semilogy(freq, pyy_avg, alpha=0.7, label=f'{label} (Y)')
            if include_x:
                plt.semilogy(freq, pxx_avg, alpha=0.7, label=f'{label} (X)')

        # Set plot properties
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Avg Power Spectral Density (PSD)')
        if title:
            plt.title(title)  # Add custom title
        if xlim:
            plt.xlim(xlim)  # Set x-axis limits if provided
        plt.legend()
        plt.grid()
        plt.tight_layout()
        plt.show()
