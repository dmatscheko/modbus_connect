# SolaX Power X3-HAC (11 kW) — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Writes require the charger unlocked

Same as the SolaX inverters: config-register writes fail while locked; unlock via
the lock/verification register first.

## Protocol document sourcing and write limits

The protocol document is manufacturer-authored but community-hosted — SolaX does
not publish it publicly. It notes an EEPROM write-cycle limit and a ~1 s minimum
interval between commands.

## The RTC is UTC-based

The RTC is UTC-based (the sync writes UTC offset + UTC time), unlike the
inverter's local-time clock.
