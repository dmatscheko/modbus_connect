# Eastron SDM-230 — caveats & limitations

Known limitations of this device file — things that are not (or not yet) fully
supported, or that you should verify against your own hardware.

## Baud-rate options track an older protocol revision

The baud-rate select in the device file (…, 5 = 1200 bps) matches the older
eastron.com.cn V1.2 protocol. The newer Eastron Europe revision of the same
document instead lists 3 = 19200 / 4 = 38400. If your meter is a newer revision
the baud-rate map may not match — both protocol PDFs are in this folder for
comparison.

## Source is a distributor mirror

Eastron gates the protocol PDF behind login on its own sites, so the copy here
came from a reputable distributor mirror (a genuine Eastron-branded document).
