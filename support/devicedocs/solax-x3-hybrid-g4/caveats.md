# SolaX Power X3-Hybrid G4 — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Writes require the inverter unlocked

Config-register writes return Modbus exception 4 (device failure) while locked.
Set the *Lock State* entity to *Unlocked* (value 2014; 6868 = Advanced) first.
SolaX has no auto-unlock; it persists until the inverter restarts.

## VPP / remote-control mode 8/9 auto-repeat is not implemented

It is a stateful recompute across ~15 remote-control registers that cannot be
expressed declaratively. The "direct" remote-control registers are write-only (no
read-back; the entity shows its last written value).

## Protocol-version-gated register meanings

Register meanings depend on the SolaX protocol-document version (the device
reports its own on holding 0x82). This file targets V1.02+; if your inverter
reports a different version, some register meanings differ — regenerate with that
version.

## Protocol document sourcing and write limits

The protocol document is manufacturer-authored but community-hosted — SolaX does
not publish it publicly. The doc also notes an EEPROM write-cycle limit and a
~1 s minimum interval between commands; avoid hammering writable registers.
