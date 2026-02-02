import pandas as pd
import os

def analyze():
    log_dir = "financial-engine/batch_logs"
    # Find latest normalization log
    norm_files = [f for f in os.listdir(log_dir) if f.startswith("normalization_")]
    if not norm_files:
        print("No normalization logs found.")
        return

    latest_norm = sorted(norm_files)[-1]
    print(f"Analyzing {latest_norm}...")
    
    try:
        df = pd.read_csv(os.path.join(log_dir, latest_norm))
        unique_files = df['filename'].unique()
        print(f"Unique files processed in normalization: {len(unique_files)}")
        
        # Breakdown by category group
        print("\nItems by Category Group:")
        print(df['category_group'].value_counts())
        
        # Confidence Stats
        print("\nConfidence Stats:")
        print(df['confidence'].describe())
        
    except Exception as e:
        print(f"Error analyzing normalization log: {e}")

    # Check errors
    error_files = [f for f in os.listdir(log_dir) if f.startswith("errors_")]
    if error_files:
        latest_error = sorted(error_files)[-1]
        print(f"\nAnalyzing {latest_error}...")
        try:
            err_df = pd.read_csv(os.path.join(log_dir, latest_error))
            print(f"Total Errors: {len(err_df)}")
            print("\nError Breakdown:")
            print(err_df['error_message'].value_counts())
        except Exception as e:
             print(f"Error analyzing error log: {e}")

if __name__ == "__main__":
    analyze()