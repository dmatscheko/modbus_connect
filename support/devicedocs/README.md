# Device Modbus register references

Primary-source Modbus documentation for every bundled device, plus a generated
`registers.md` per device tabulating the registers the Modbus Connect device file
reads and writes (register · table · Modbus function code · data type / conversion).

| Device | Registers | Primary source | Authority | Addresses |
| --- | --- | --- | --- | --- |
| Dimplex Sole/Wasser-Wärmepumpe SI 11TU | [`dimplex-si-11tu`](./dimplex-si-11tu/registers.md) (128) | [Dimplex — NWPM Modbus TCP Datenpunktliste (Wärmepumpenmanager)](https://dimplex.atlassian.net/wiki/spaces/DW/pages/2873393288/NWPM+Modbus+TCP) | official | verified |
| Eastron SDM-230 | [`eastron-sdm230`](./eastron-sdm230/registers.md) (25) | [Eastron SDM230-Modbus — Modbus Protocol Implementation](https://downloads.innon.com/hubfs/downloads.innon.com/Power%20Meters/SDM230-MOD-MID/Manuals/SDM230-PROTOCOL.pdf) | official | verified |
| Eastron SDM-630 | [`eastron-sdm630`](./eastron-sdm630/registers.md) (85) | [Eastron SDM630-Modbus — Modbus Protocol Implementation](https://www.eastroneurope.com/images/uploads/products/protocol/SDM630_MODBUS_Protocol.pdf) | official | verified |
| ebyte ME31-AXAX404 | [`ebyte-me31-axax404`](./ebyte-me31-axax404/registers.md) (8) | [EBYTE — ME31-AXAX4040 User Manual (EN)](https://www.cdebyte.com/products/ME31-AXAX4040/4) | official | verified |
| Finder 7M.24 | [`finder-7m24`](./finder-7m24/registers.md) (19) | [Finder — MODBUS Communication Protocol 7M.24 / 7M.38](https://cdn.findernet.com/app/uploads/2021/09/20090052/Modbus-7M24-7M38_v2_30062021.pdf) | official | verified |
| Finder 7M.38 | [`finder-7m38`](./finder-7m38/registers.md) (35) | [Finder — MODBUS Communication Protocol 7M.24 / 7M.38](https://cdn.findernet.com/app/uploads/2021/09/20090052/Modbus-7M24-7M38_v2_30062021.pdf) | official | verified |
| Fröling GmbH BWP300 PV | [`froeling-bwp300-pv`](./froeling-bwp300-pv/registers.md) (44) | — none found — | none | — |
| Growatt MIC 2500TL-X | [`growatt-mic-2500tl-x`](./growatt-mic-2500tl-x/registers.md) (60) | [Growatt Inverter Modbus RTU Protocol (a.k.a. Protocol II)](https://github.com/johanmeijer/grott/blob/master/documentatie/Growatt-Inverter-Modbus-RTU-Protocol-II-V1-24-English-new.pdf) | manufacturer doc, community-hosted | verified |
| Growatt MIN 6000TL-XH | [`growatt-min-6000tl-xh`](./growatt-min-6000tl-xh/registers.md) (77) | [Growatt Inverter Modbus RTU Protocol (a.k.a. Protocol II)](https://github.com/johanmeijer/grott/blob/master/documentatie/Growatt-Inverter-Modbus-RTU-Protocol-II-V1-24-English-new.pdf) | manufacturer doc, community-hosted | verified |
| Growatt MOD 10KTL3-XH | [`growatt-mod-10ktl3-xh`](./growatt-mod-10ktl3-xh/registers.md) (77) | [Growatt Inverter Modbus RTU Protocol (a.k.a. Protocol II)](https://github.com/johanmeijer/grott/blob/master/documentatie/Growatt-Inverter-Modbus-RTU-Protocol-II-V1-24-English-new.pdf) | manufacturer doc, community-hosted | verified |
| Growatt MOD 6000TL-X | [`growatt-mod-6000tl-x`](./growatt-mod-6000tl-x/registers.md) (77) | [Growatt Inverter Modbus RTU Protocol (a.k.a. Protocol II)](https://github.com/johanmeijer/grott/blob/master/documentatie/Growatt-Inverter-Modbus-RTU-Protocol-II-V1-24-English-new.pdf) | manufacturer doc, community-hosted | verified |
| Growatt SPH3600TL BL_UP | [`growatt-sph-3600tl-bl-up`](./growatt-sph-3600tl-bl-up/registers.md) (31) | [Growatt Inverter Modbus RTU Protocol (a.k.a. Protocol II)](https://github.com/johanmeijer/grott/blob/master/documentatie/Growatt-Inverter-Modbus-RTU-Protocol-II-V1-24-English-new.pdf) | manufacturer doc, community-hosted | verified |
| Husdata H60 | [`husdata-h60`](./husdata-h60/registers.md) (9) | [Husdata — H1 Interface Developer’s Manual (Common-register ID-code table)](https://husdata.se/wp-content/uploads/2015/11/H1-Manual-10.184.pdf) | official | partial |
| Pichler Lüftungsgerät LG 150 - LG 250 | [`pichler-lg150-lg250`](./pichler-lg150-lg250/registers.md) (192) | [Pichler / LS-Control — Modbus register list (controller ES1015, LG150AB/LG250A)](https://www.pichlerluft.at/unterlagen.html?file=files/content/downloads/LOGIN/LG%20150AB-LG250A/LIST_Modbus_ES1015_FW_LG150AB_LG250A_v2.0.0.xlsx) | official | verified |
| Pichler Lüftungsgerät LG 350 - LG 450 | [`pichler-lg350-lg450`](./pichler-lg350-lg450/registers.md) (186) | [Pichler / LS-Control — Modbus register list (controller ES2020, LG350/450/740/1000)](https://www.pichlerluft.at/unterlagen.html?file=files/content/downloads/LOGIN/LG%20350_LG%20450_LG%20740_LG%201000%20SK/LIST_Modbus_ES2020_FW_LG350_LG450_LG740_LG1000_v2.0.0.xlsx) | official | verified |
| Salda RIS / RIRS (MCB) | [`salda-ris-mcb`](./salda-ris-mcb/registers.md) (9) | [Salda — MCB Modbus register table (v1.29) + MCB / mini-MCB manual](http://salda.lt/mcb/downloads/doc/MCB%201.29%20Modbus%20table%202026-04-22.xlsx) | official | partial |
| Schneider Electric Altivar ATV312 | [`schneider-atv312`](./schneider-atv312/registers.md) (74) | [Schneider Electric — Altivar 312 Communication Variables Manual (BBV51701)](https://www.se.com/ww/en/download/document/BBV51701/) | official | verified |
| Schneider Electric Altivar ATV312 Expert | [`schneider-atv312-expert`](./schneider-atv312-expert/registers.md) (11) | [Schneider Electric — Altivar 312 Communication Variables Manual (BBV51701)](https://www.se.com/ww/en/download/document/BBV51701/) | official | verified |
| SolaX Power X3-HAC (11 kW) | [`solax-x3-hac`](./solax-x3-hac/registers.md) (84) | [SolaX — X1/X3-HAC EV Charger Modbus RTU/TCP Communication Protocol](https://github.com/user-attachments/files/18746087/X1.X3-HAC.EV.Charger.Modbus.TCP.RTU.V1.0.0-EN.pdf) | manufacturer doc, community-hosted | verified |
| SolaX Power X3-Hybrid G4 | [`solax-x3-hybrid-g4`](./solax-x3-hybrid-g4/registers.md) (447) | [SolaX — Energy Storage Inverter Modbus TCP & RTU Communication Protocol (Hybrid X1&X3-G4)](https://github.com/user-attachments/files/19076476/Solax.Hybrid_X1.X3-G4_ModbusTCP.RTU_V3.36-English_240611.1.pdf) | manufacturer doc, community-hosted | verified |
| Varmann Qtherm | [`varmann-qtherm`](./varmann-qtherm/registers.md) (24) | [VARMANN — Exchange Protocol with convector control units](https://www.varmann.ru/download/downloads_files/Exchange_Protocol_with_VARMANN_convector_control_units.pdf) | official | verified |
| Waveshare Modbus POE ETH Relay 30CH | [`waveshare-modbus-poe-eth-relay-30ch`](./waveshare-modbus-poe-eth-relay-30ch/registers.md) (31) | [Waveshare Wiki — Modbus POE ETH Relay (30CH)](https://www.waveshare.com/wiki/Modbus_POE_ETH_Relay_30CH) | official | verified |
| Waveshare Modbus RTU Relay (D) | [`waveshare-modbus-rtu-relay-d`](./waveshare-modbus-rtu-relay-d/registers.md) (17) | [Waveshare Wiki — Modbus RTU Relay (D)](https://www.waveshare.com/wiki/Modbus_RTU_Relay_(D)) | official | verified |

**Authority** — *official*: from the manufacturer's own site/CDN/wiki. *manufacturer doc,
community-hosted*: a genuine manufacturer document the vendor doesn't publish publicly
(SolaX, Growatt), mirrored by a reputable community project. *none*: no public register document exists.

**Addresses** — device-file addresses cross-checked against the source: *verified* / *partial*.
