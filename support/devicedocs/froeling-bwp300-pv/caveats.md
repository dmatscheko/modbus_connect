# Fröling GmbH BWP300 PV — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## No manufacturer Modbus documentation exists

Fröling publishes no register map for the BWP 300 PV (its official technical
documents are storage-tank manuals with no Modbus content). The register map in
this device file (holding 4–33, input 0–119) is community/vendor-supplied and NOT
verified against any Fröling source — treat every address, type and scaling as
unconfirmed.

## Status/alarm bitfields were hand-repaired

The status/alarm bitfields were hand-repaired to 0-indexed bit positions during
the upstream conversion; verify against your controller.

## Third-party OEM controller

The underlying controller appears to be a third-party OEM unit, so the map may
vary by firmware.
