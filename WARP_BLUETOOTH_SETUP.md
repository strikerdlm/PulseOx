# Warp Environment with Bluetooth Support

## Environment Details

**Environment Name:** `pulseox-ble`  
**Environment ID:** `jMpnbHEMRkjecBxJqJ4EiD`  
**Docker Image:** `5trikerdlm/warp-pulseox:latest`  
**Repository:** `strikerdlm/PulseOx`

## What This Environment Provides

This Warp environment has been configured to support Bluetooth Low Energy (BLE) devices on Linux. The custom Docker image includes:

1. **Conda/Mamba** - Python 3.11 environment manager (from `condaforge/mambaforge:24.9.0-0`)
2. **Bluetooth Stack:**
   - `bluez` - Linux Bluetooth protocol stack
   - `rfkill` - Tool to enable/disable wireless devices
   - `dbus` - Inter-process communication system required by BlueZ

3. **Automatic Setup:**
   - Unblocks Bluetooth using `rfkill unblock bluetooth`
   - Starts D-Bus service
   - Starts Bluetooth daemon (`bluetoothd`)
   - Creates conda environment from `environment.yml`

## Docker Image Architecture

The custom Docker image (`5trikerdlm/warp-pulseox:latest`) is built for **AMD64/x86_64** architecture and includes an entrypoint script that automatically:

```bash
#!/bin/bash
set -e

# Unblock Bluetooth if blocked
rfkill unblock bluetooth || true

# Start D-Bus service
service dbus start

# Start Bluetooth daemon in background
bluetoothd &

# Execute the command passed to docker run
exec "$@"
```

## Important: Runtime Requirements

**⚠️ CRITICAL:** For Bluetooth to work in the Warp environment, the container **MUST** be run with these Docker flags:

- `--privileged` - Grants extended privileges to access Bluetooth hardware
- `--net=host` - Shares the host's network namespace (required for BlueZ)

### Why These Flags Are Needed

1. **`--privileged`**: Bluetooth requires direct access to hardware devices (`/dev/rfkill`, HCI adapters) that are normally restricted in containers.

2. **`--net=host`**: The BlueZ Bluetooth stack uses D-Bus for communication and needs access to the host's network interfaces to control Bluetooth adapters.

### How to Request These Flags

**When using Warp Platform automation (Ambient Agents, integrations, etc.):**

You'll need to configure the host/runner to use these Docker flags. This may require:
- Modifying the host configuration
- Working with Warp support to enable these flags for your environment
- Using a self-hosted runner where you control Docker execution parameters

**For local testing:**
```bash
docker run --privileged --net=host -it 5trikerdlm/warp-pulseox:latest /bin/bash
```

## Host System Considerations

### Bluetooth Service Conflicts

**IMPORTANT:** If running exclusive Bluetooth access mode (container controls Bluetooth):

On the **host** machine, you may need to stop the Bluetooth service before starting the container:

```bash
# Stop host Bluetooth service (Ubuntu/Debian)
sudo systemctl stop bluetooth

# Or kill the Bluetooth daemon
sudo killall -9 bluetoothd
```

**Alternative - Shared Mode:** The container can share Bluetooth access with the host by mounting the D-Bus socket:
```bash
docker run -v /var/run/dbus/:/var/run/dbus/:z --privileged 5trikerdlm/warp-pulseox:latest
```

However, this approach may have limitations for BLE scanning.

## Testing the Environment

Once the environment is running with proper flags, you can test Bluetooth functionality:

```bash
# Inside the container:

# Check if Bluetooth adapter is detected
hciconfig

# List Bluetooth devices
hcitool dev

# Scan for BLE devices
hcitool lescan

# Or use the PulseOx CLI after activating conda env
conda activate pulseox
python -m pulseox.cli --scan
```

## GitHub Authorization

The repository `strikerdlm/PulseOx` currently has **read-only access**. To enable full access (creating PRs, pushing changes):

Authorize Warp with GitHub: https://github.com/apps/warp-agent/installations/new?state=e56c9bc1-a8ed-43bc-b029-849a65d83796

## Using with Integrations

Connect this environment to integrations:

```bash
warp-terminal integration create [provider] --environment jMpnbHEMRkjecBxJqJ4EiD
```

Where `[provider]` can be: `linear` or `slack`

For more details: `warp-terminal integration create --help`

## Troubleshooting

### Bluetooth Not Working

1. **Verify Docker flags:** Ensure `--privileged` and `--net=host` are being used
2. **Check rfkill status:** Run `rfkill list` to see if Bluetooth is blocked
3. **Verify services:** Check that D-Bus and bluetoothd are running:
   ```bash
   ps aux | grep dbus
   ps aux | grep bluetoothd
   ```

### Permission Issues

If you see "Permission denied" errors:
- Ensure the container is running with `--privileged`
- Check that the user has permissions to access `/dev/rfkill` and HCI devices

### D-Bus Connection Issues

If you see D-Bus connection errors:
- Verify D-Bus is running: `service dbus status`
- Restart D-Bus: `service dbus restart`
- Check D-Bus socket exists: `ls -la /var/run/dbus/system_bus_socket`

## Platform-Specific Notes

### Windows (WSL2)
Bluetooth passthrough from Windows to WSL2 containers is **not supported** by default. You may need additional tools or drivers.

### macOS
Docker Desktop on macOS does not support Bluetooth passthrough to containers. This environment is designed for **Linux hosts only**.

### Linux
Fully supported on Linux hosts with Bluetooth hardware. Tested on Ubuntu.

## References

Based on research from:
- [Stack Overflow: Accessing Bluetooth dongle from inside Docker](https://stackoverflow.com/questions/28868393/accessing-bluetooth-dongle-from-inside-docker)
- [Docker Forums: Docker Bluetooth and Bluez without --privileged --net=host](https://forums.docker.com/t/docker-bluetooth-and-bluez-without-privileged-net-host/125955)

## Next Steps

1. **Authorize GitHub access** (optional, for full repo access)
2. **Configure host/runner** to use `--privileged --net=host` flags
3. **Test the environment** with a simple BLE scan
4. **Connect to integrations** as needed
