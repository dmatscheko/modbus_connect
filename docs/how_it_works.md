# How it works

What Modbus Connect does between your device and Home Assistant: how it reads,
how it writes, and how it copes when a device misbehaves. You do not need any
of this to use the integration — it explains what you see.

- [The four design ideas](#the-four-design-ideas)
- [Reading: the poll cycle](#reading-the-poll-cycle)
- [Writes](#writes)
- [Read health](#read-health)
- [Registers the device refuses](#registers-the-device-refuses)
- [When the device is offline](#when-the-device-is-offline)

## The four design ideas

1. **Block reads.** Instead of one Modbus round trip per entity, each poll
   merges everything into as few reads as possible. Overlapping and adjacent
   registers combine, and small unused holes are bridged, because reading a few
   unneeded registers is cheaper than asking twice.
2. **Home Assistant is not shadowed.** Every entity's `ha:` block is passed to
   the real Home Assistant entity description and validated against it. Any
   entity feature Home Assistant supports can be set there, and a typo fails
   loudly, naming the file, the entity and the valid choices.
3. **Symmetric conversions.** Whatever the integration can decode, it can also
   encode for writing: scaling, enum maps, multi-register sums, masked bit
   fields. Only `flags` is inherently read-only.
4. **Templates, not code.** Derived values and composite entities (a thermostat
   built from three registers) are declared as Jinja templates over the
   device's values. Device quirks become a few lines of YAML, not a plugin.

## Reading: the poll cycle

The integration polls. Each cycle it

1. collects every entity that is due,
2. plans the smallest set of block reads that covers their registers,
3. executes them over one shared connection per gateway or serial port,
4. decodes all values from the result.

Blocks never exceed the device's `max_register_read` or the Modbus protocol
limit of 125 registers. With the bundled files, an Eastron SDM630 goes from 85
requests per poll to 27 (7 if the file allowed 100 registers per read), and a
Pichler LG350 with every group enabled from 184 to 7.

**How often.** The device file sets each entity's interval. The *Minimum
update interval* in the entry's options is only a floor: it slows polling
down, never speeds it up. The exact precedence is in the
[device file reference](device_files.md#read-planning-and-polling).

**What is read.** Only entities that exist. Entities hidden through
[entity groups](entity_groups.md) drop out of the read plan.

**Addresses the device chokes on.** Unused addresses a device refuses when a
read is bridged across them are learned from the failed reads and routed
around. A device file can also declare them up front (`bad_addresses`,
`split_before`).

## Writes

- A write goes through the same conversions as a read, in reverse. A value
  that cannot be encoded — one that is not in the entity's `map`, for example
  — is rejected instead of written.
- A write is **confirmed by reading the register back** straight away. If the
  device took the write but the read-back fails, that is logged as a failed
  read, not reported as a failed write.
- A value the register **already holds is not written again**. Many devices
  keep settings in EEPROM or flash, which survives only a limited number of
  write cycles; an automation re-sending the same setpoint would otherwise
  wear it out. Command registers that must act every time opt out with
  `write_always` in the device file.

## Read health

The companion *Configuration* device carries three diagnostics:

| Entity | What it tells you |
| --- | --- |
| **Reads per refresh** | How many block reads a full refresh issues. It is usually far below the number of entities — that gap is what block reading saves. |
| **Read failures** | A problem indicator: on when a read failed within the last 5 minutes. |
| **Failed reads** | The running total of failed reads. |

Both failure entities count unrecovered failures only, so a healthy device
never writes them to the recorder.

## Registers the device refuses

A register that keeps failing while the device answers everything else is the
signature of a wrong address in a device file. Such a register is
**quarantined**:

- its entity becomes unavailable,
- its registers leave the read plan, so the healthy ones are not slowed down,
- a probe every 10 minutes lifts the quarantine as soon as the device serves
  the register again.

You are told in two places: the log warns with the entity and its address, and
a **repair issue** under *Settings → System → Repairs* names the entity, its
register and the device file. The issue clears itself when the register
recovers. A device file that fails to load raises a repair issue as well.

Only a register that has **never answered** can be quarantined. Once the device
has served it on two polls in a row it is known alive and stays in the read
plan through any later failure. So a device that is power-cycled — timing out,
then refusing reads while it boots — is polled again the moment it answers.

*Download diagnostics* on the device page lists `quarantined`, `not_yet_alive`
and the failure count per entity (`failed_reads_by_key`, worst first).

What to do about a quarantined register is covered in
[troubleshooting](troubleshooting.md#some-entities-are-unavailable).

## When the device is offline

If the device does not answer at all, every entity becomes unavailable. The
integration logs once when the device becomes unreachable and once when it
recovers, and retries with an exponentially growing pause of up to 5 minutes,
so an offline device does not hammer the gateway.
