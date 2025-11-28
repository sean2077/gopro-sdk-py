# Troubleshooting

This page covers common issues and their solutions when using GoPro SDK.

## Connection Issues

### Camera Not Found During BLE Scan

**Symptoms:**

- `scan_for_cameras()` returns empty list
- Camera not discoverable

**Solutions:**

1. **Enable Pairing Mode on Camera**
   - Go to camera menu: **Preferences → Connections → Connect Device**
   - Camera will enter pairing mode and become discoverable
   - The pairing mode typically times out after ~3 minutes

2. **Check Bluetooth Status**
   - Ensure Bluetooth is enabled on your computer
   - Make sure no other device is currently connected to the camera via BLE

3. **Restart Camera**
   - Power off the camera completely
   - Wait a few seconds, then power on
   - Try scanning again

---

### COHN Connection Timeout / HTTP Connection Failed

**Symptoms:**

- `BleConnectionError: Failed to get COHN credentials`
- HTTP requests timeout
- Camera was working before but now fails to connect

**Common Cause:**

This typically happens when camera was previously connected to a different WiFi network or PC. The camera caches old COHN credentials which conflict with the new environment.

**Solutions:**

1. **Clear COHN Cache on Camera**

   Navigate to camera menu:

   - **Preferences → Connections → Clear COHN Cache** (or similar, varies by model)

   Then retry connection.

2. **Reset Camera Network Settings**

   Different GoPro models have different reset procedures:

   | Model  | Reset Path                                    |
   | ------ | --------------------------------------------- |
   | HERO13 | Preferences → Connections → Reset Connections |
   | HERO12 | Preferences → Connections → Reset Connections |
   | HERO11 | Preferences → Connections → Reset Connections |
   | HERO10 | Preferences → Reset → Reset Connections       |

   After reset, you'll need to reconfigure WiFi connection.

3. **Delete Local Credentials**

   Delete the local credentials file and let the SDK fetch fresh credentials:

   ```python
   import os

   # Delete the credentials file
   if os.path.exists("cohn_credentials.json"):
       os.remove("cohn_credentials.json")

   # Reconnect - SDK will fetch new credentials
   async with GoProClient("1332", offline_mode=False,
                          wifi_ssid="MyWiFi", wifi_password="pass") as client:
       pass
   ```

4. **Use `reset_cohn()` Method**

   If you can establish BLE connection but COHN fails:

   ```python
   async with GoProClient("1332") as client:
       # Reset COHN certificate
       await client.reset_cohn()
       # Then switch to online mode
       await client.switch_to_online_mode(wifi_ssid="MyWiFi", wifi_password="pass")
   ```

---

### WiFi Connection Failed

**Symptoms:**

- `BleConnectionError: WiFi connection timeout`
- Camera not connecting to specified WiFi

**Solutions:**

1. **Verify WiFi Credentials**
   - Double-check SSID spelling (case-sensitive)
   - Verify password is correct

2. **Check WiFi Compatibility**
   - GoPro cameras support 2.4GHz and 5GHz WiFi
   - Some older models may have issues with certain WiFi security protocols
   - Try a simpler WiFi network if available

3. **Ensure Camera is in Range**
   - Move camera closer to WiFi router
   - Avoid interference from other devices

4. **Check Router Settings**
   - Ensure DHCP is enabled
   - Check if MAC filtering is blocking the camera
   - Some enterprise networks may block GoPro devices

---

### Camera Disconnects During Operation

**Symptoms:**

- Random disconnections during recording or preview
- `BleConnectionError` after some time

**Solutions:**

1. **Keep-Alive Signal**

   Send periodic keep-alive signals to prevent timeout:

   ```python
   import asyncio

   async def keep_alive_loop(client):
       while True:
           await asyncio.sleep(30)  # Every 30 seconds
           try:
               await client.set_keep_alive()
           except Exception:
               pass
   ```

2. **Check Battery Level**
   - Low battery can cause unstable connections
   - Use external power if available

3. **Reduce WiFi Interference**
   - Move away from other 2.4GHz/5GHz devices
   - Avoid crowded WiFi channels

---

## Preview Issues

### Preview Stream Not Working

**Symptoms:**

- `start_preview()` succeeds but no video in player
- UDP stream not receiving data

**Solutions:**

1. **Check Firewall Settings**
   - Ensure UDP port 8554 (default) is not blocked
   - Add exception for your application in firewall

2. **Verify Camera Mode**
   - Camera must not be in Webcam mode
   - Stop any ongoing recording first

3. **Use Correct Stream URL**

   ```python
   stream_url = await client.start_preview(port=8554)
   print(f"Open in VLC: {stream_url}")
   # Output: udp://127.0.0.1:8554
   ```

4. **Test with VLC**
   - Open VLC → Media → Open Network Stream
   - Enter: `udp://@:8554`
   - This can help diagnose if issue is with SDK or playback

---

## Media Download Issues

### Download Fails or Incomplete

**Symptoms:**

- `download_file()` raises exception
- Downloaded files are corrupted

**Solutions:**

1. **Enable Turbo Mode for Large Files**

   ```python
   await client.set_turbo_mode(True)
   downloaded = await client.download_file(media, save_path)
   await client.set_turbo_mode(False)
   ```

2. **Check Available Disk Space**
   - Ensure sufficient space for the file
   - GoPro video files can be very large (several GB)

3. **Use Stable Network**
   - Avoid downloading over weak WiFi
   - Consider wired connection if available

---

## Webcam Mode Issues

### Webcam Not Starting

**Symptoms:**

- `start_webcam()` fails
- Webcam mode not responding

**Solutions:**

1. **Ensure Online Mode**
   - Webcam features require online mode (BLE + WiFi)
   - Make sure COHN connection is established

2. **Check Camera State**
   - Camera must not be recording
   - Exit any other modes first using `webcam_exit()`

3. **Exit Other Camera Apps**
   - Close any application that might be using the camera stream
   - Only one application can use webcam at a time

---

## General Tips

### Enable Debug Logging

For detailed diagnostics, enable debug logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)

# Or for specific modules
logging.getLogger("gopro_sdk").setLevel(logging.DEBUG)
```

### Check Camera Firmware

Ensure camera firmware is up to date:

- Use GoPro Quik app to update firmware
- Some SDK features require minimum firmware versions

### Use Offline Mode When Possible

If you don't need preview/download features, use offline mode for more reliable operation:

```python
# More stable - BLE only
async with GoProClient("1332") as client:
    await client.start_recording()
```

---

## Getting Help

If you're still experiencing issues:

1. Check the [GitHub Issues](https://github.com/sean2077/gopro-sdk-py/issues) for similar problems
2. Open a new issue with:
   - GoPro model and firmware version
   - Python version and OS
   - Debug logs
   - Minimal code to reproduce the issue
