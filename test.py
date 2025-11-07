import time
from pylsl import StreamInfo, StreamOutlet

# --- 1. Set up the LSL Stream Info ---
# We create a stream named 'PsychoPyMarkers' with type 'Markers'.
# It has 1 channel (for the trigger string)
# The sample rate is 0.0 because triggers are irregular (event-based).
# The channel format is 'string'.
# A unique source_id is good practice.
info = StreamInfo(name='Trigger',
                  type='Markers',
                  channel_count=1,
                  nominal_srate=0.0,
                  channel_format='string',
                  source_id='my_psychopy_session_12345')

# --- 2. Create the LSL Outlet ---
# This is the object that will actually send the data.
outlet = StreamOutlet(info)

print("LSL Outlet created. Now sending triggers...")
print("Look for a stream named 'Trigger' in your Aurora software.")
print("Press Ctrl+C in the console to stop.")

# --- 3. The Sending Loop ---
# This will run forever, sending a new trigger every 2 seconds.
trigger_count = 1
try:
    while True:
        # Define the trigger message
        marker_string = f"Trigger_{trigger_count}"
        
        # Send the trigger string
        # Note: push_sample() expects a list or tuple, 
        # even for a single channel.
        outlet.push_sample([marker_string])
        
        print(f"Sent: {marker_string}")
        
        # Wait for 2 seconds before sending the next one
        time.sleep(2)
        trigger_count += 1

except KeyboardInterrupt:
    print("\nStopping the script.")
    # The outlet will be closed automatically when the script exits.