"""
Builds trains.csv: every scheduled passenger train over the Thaltej crossing
(23.058006, 72.503175), with the weekday(s) and time it reaches the crossing.

Run days come from ixigo (days at origin) shifted by the train's day number at the
reference station. Timings from ixigo/erail (Oct 2026). Delays: trainspnrstatus 7-day averages.

Crossing is 1.13 km NE of Ambli Road (ABD), between ABD and Chandlodiya (CLDY).
Offsets to the crossing:
  down (ADI -> VG): ADI dep +22 | SBT dep +12 | CLDY dep +5 | ABD arr -2
  up   (VG -> ADI): VG dep +35  | ABD dep +2  | CLDY arr -5
"""
import pandas as pd

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
ALL = ",".join(DAYS)
OFF = {("down", "ADI_dep"): 22, ("down", "SBT_dep"): 12, ("down", "CLDY_dep"): 5,
       ("down", "ABD_arr"): -2, ("up", "VG_dep"): 35, ("up", "ABD_dep"): 2,
       ("up", "CLDY_arr"): -5}

# (train_no, name, direction, origin_days, ref_point, ref_time, day_no_at_ref, halts_ABD, avg_delay)
T = [
    # ---- down: Ahmedabad -> Viramgam ----
    ("22989", "BDTS MHV EXP", "down", "Wed,Fri", "ADI_dep", "00:35", 2, 0, 11),
    ("22974", "PURI GIMB SF", "down", "Sat", "ADI_dep", "00:35", 3, 0, None),
    ("22963", "BDTS BVC SFAST", "down", "Mon", "ADI_dep", "00:35", 2, 0, None),
    ("20819", "PURI OKHA SF", "down", "Sun", "ADI_dep", "00:45", 3, 0, None),
    ("20803", "VSKP GIMB SF", "down", "Thu", "ADI_dep", "00:45", 3, 0, 3),
    ("16733", "RMM OKHA EXP", "down", "Fri", "ADI_dep", "01:05", 4, 0, 9),
    ("19255", "SURAT MAHUVA EX", "down", "Mon,Tue,Thu,Sat,Sun", "ADI_dep", "01:20", 2, 0, 6),
    ("19559", "TPTY OKHA EXP", "down", "Thu", "ADI_dep", "01:20", 3, 0, None),
    ("22955", "KUTCH EXPRESS", "down", ALL, "ADI_dep", "01:30", 1, 0, 13),
    ("12971", "BDTS BVC SF EXP", "down", ALL, "ADI_dep", "02:40", 1, 0, 11),
    ("12942", "PARASNATH EXP", "down", "Thu", "ADI_dep", "03:35", 3, 0, 5),
    ("14311", "ALA HAZRAT EXP", "down", "Tue,Thu,Sat", "CLDY_dep", "03:40", 2, 0, None),
    ("22907", "MAO HAPA SF EXP", "down", "Fri", "ADI_dep", "03:50", 2, 0, 7),
    ("19108", "BHAVNAGAR EXP", "down", "Mon", "ABD_arr", "04:00", 3, 1, None),
    ("19270", "PBR EXPRESS", "down", "Mon,Sun", "CLDY_dep", "04:38", 3, 0, None),
    ("22945", "SAURASHTRA MAIL", "down", ALL, "CLDY_dep", "05:26", 1, 0, 7),
    ("20686", "SBC GIMB SF EXP", "down", "Sat", "ADI_dep", "05:40", 3, 0, 9),
    ("12906", "SHM PBR SUF EXP", "down", "Fri,Sat", "ADI_dep", "06:05", 3, 0, 218),
    ("22906", "SHM OKHA SF EXP", "down", "Tue", "ADI_dep", "06:05", 3, 0, None),
    ("22925", "OKHA VANDE BHARAT", "down", "Mon,Wed,Thu,Fri,Sat,Sun", "ABD_arr", "06:23", 1, 1, None),
    ("16334", "TVC VRL EXP", "down", "Mon", "ADI_dep", "06:50", 3, 0, None),
    ("16336", "NCJ GIMB EXP", "down", "Tue", "ADI_dep", "06:50", 3, 0, None),
    ("16338", "ERS OKHA EXP", "down", "Wed,Fri", "ADI_dep", "06:50", 3, 0, None),
    ("11092", "PUNE BHUJ EXP", "down", "Mon", "ADI_dep", "07:30", 2, 0, None),
    ("11088", "PUNE VRL EXP", "down", "Thu", "ADI_dep", "07:35", 2, 0, None),
    ("22923", "JAM HUMSAFAR", "down", "Mon,Thu,Sat", "ADI_dep", "07:55", 2, 0, None),
    ("11464", "JBP SOMNATH EXP", "down", "Tue,Wed,Thu,Sat,Sun", "CLDY_dep", "08:31", 2, 0, None),
    ("11466", "JBP SOMNATH EXP", "down", "Mon,Fri", "CLDY_dep", "08:31", 2, 0, None),
    ("12950", "KAVIGURU EXP", "down", "Sun", "ADI_dep", "08:40", 3, 0, None),
    ("20936", "INDB GIMB SF", "down", "Sun", "ADI_dep", "09:05", 2, 0, None),
    ("22940", "BSP OKHA SF EXP", "down", "Mon", "ADI_dep", "09:35", 2, 0, None),
    ("19119", "GNC SOMNATH EXP", "down", ALL, "ABD_arr", "10:55", 1, 1, None),
    ("12474", "SARVODAYA EXP", "down", "Thu", "ADI_dep", "12:15", 2, 0, None),
    ("12476", "SVDK HAPA EXP", "down", "Mon", "ADI_dep", "12:15", 2, 0, None),
    ("12478", "SVDK JAM EXP", "down", "Sun", "ADI_dep", "12:15", 2, 0, None),
    ("20967", "SC PBR SF EXP", "down", "Wed", "ADI_dep", "13:25", 2, 0, None),
    ("12755", "COA BVC SF EXP", "down", "Thu", "ADI_dep", "13:35", 2, 0, None),
    ("16614", "CBE RJT EXP", "down", "Fri", "ADI_dep", "13:35", 2, 0, None),
    ("22718", "RAJKOT SF EXP", "down", "Mon,Tue,Sat", "ADI_dep", "13:35", 2, 0, None),
    ("15636", "GHY OKHA EXP", "down", "Mon", "ADI_dep", "13:50", 3, 0, None),
    ("15668", "KYQ GIMB EXP", "down", "Wed", "ADI_dep", "13:50", 3, 0, None),
    ("94801", "NAMO BHARAT RAPID RAIL", "down", "Mon,Tue,Wed,Thu,Fri,Sun", "ABD_arr", "17:48", 1, 1, None),
    ("22938", "REWA RJT SUP EXP", "down", "Mon", "ADI_dep", "17:45", 2, 0, None),
    ("22959", "INTERCITY EXP", "down", ALL, "ABD_arr", "18:03", 1, 1, 19),
    ("15045", "GKP OKHA EXP", "down", "Thu", "CLDY_dep", "18:07", 2, 0, None),
    ("19567", "VIVEK EXPRESS", "down", "Sun", "ADI_dep", "18:20", 3, 0, None),
    ("69185", "ADI-VG MEMU", "down", "Mon,Tue,Wed,Thu,Fri,Sun", "ABD_arr", "19:09", 1, 1, None),
    ("19015", "SAURASHTRA EXP", "down", ALL, "CLDY_dep", "20:45", 1, 0, 29),
    ("22957", "SOMNATH EXPRESS", "down", ALL, "CLDY_dep", "22:12", 1, 0, None),
    ("19217", "SAURASHTRA JANTA", "down", ALL, "CLDY_dep", "22:43", 1, 0, 20),
    ("22951", "BDTS GIMB SFAST", "down", "Fri", "ADI_dep", "22:45", 1, 0, 8),
    ("22970", "BNRS OKHA SF", "down", "Sat", "ADI_dep", "22:45", 2, 0, None),
    ("20909", "TVCN PBR SF EXP", "down", "Sun", "ADI_dep", "22:45", 2, 0, None),
    ("20938", "DEE PBR EXPRESS", "down", "Mon,Thu", "CLDY_dep", "23:05", 1, 0, None),
    ("20907", "SAYAJINAGRI EXP", "down", ALL, "ADI_dep", "23:35", 1, 0, 35),
    # ---- up: Viramgam -> Ahmedabad ----
    ("22990", "MHV BDTS EXP", "up", "Thu,Sat", "VG_dep", "00:37", 2, 0, None),
    ("22924", "BDTS HUMSAFAR", "up", "Tue,Fri,Sun", "VG_dep", "00:37", 2, 0, None),
    ("19256", "MAHUVA SURAT EX", "up", "Mon,Tue,Wed,Fri,Sun", "VG_dep", "01:02", 2, 0, None),
    ("22956", "KUTCH EXPRESS", "up", ALL, "VG_dep", "01:28", 1, 0, None),
    ("22908", "HAPA MAO SF EXP", "up", "Wed", "VG_dep", "01:50", 2, 0, None),
    ("20910", "PBR TVCN SF EXP", "up", "Thu", "VG_dep", "01:50", 2, 0, None),
    ("22939", "OKHA BSP SF EXP", "up", "Sat", "VG_dep", "02:42", 2, 0, None),
    ("22952", "GIMB BDTS SFAST", "up", "Thu", "VG_dep", "02:42", 2, 0, None),
    ("20804", "GIMB VSKP SF EX", "up", "Sun", "VG_dep", "02:42", 2, 0, None),
    ("20820", "OKHA PURI EXP", "up", "Wed", "VG_dep", "02:42", 2, 0, None),
    ("20908", "SAYAJINAGRI EXP", "up", ALL, "VG_dep", "03:37", 1, 0, None),
    ("20937", "PBR DEE EXPRESS", "up", "Tue,Sat", "CLDY_arr", "04:05", 2, 0, None),
    ("19269", "PBR MFP EXPRESS", "up", "Thu,Fri", "CLDY_arr", "04:05", 2, 0, None),
    ("22958", "SOMNATH EXPRESS", "up", ALL, "CLDY_arr", "05:01", 1, 0, None),
    ("19016", "SAURASHTRA EXP", "up", ALL, "CLDY_arr", "06:38", 1, 0, None),
    ("19560", "OKHA TPTY EXP", "up", "Mon", "VG_dep", "06:52", 2, 0, None),
    ("15046", "OKHA GKP EXP", "up", "Sun", "CLDY_arr", "07:32", 2, 0, None),
    ("12756", "BVC COA SF EXP", "up", "Sat", "VG_dep", "08:17", 1, 0, None),
    ("16613", "RJT CBE EXP", "up", "Sun", "VG_dep", "08:17", 1, 0, None),
    ("19568", "VIVEK EXPRESS", "up", "Fri", "VG_dep", "08:17", 1, 0, None),
    ("20968", "PBR SC SF EXP", "up", "Tue", "VG_dep", "08:17", 1, 0, None),
    ("22717", "RJT SC SUP EXP", "up", "Mon,Wed,Thu", "VG_dep", "08:17", 1, 0, None),
    ("69186", "VG-ADI MEMU", "up", ALL, "ABD_dep", "08:31", 1, 1, None),
    ("19107", "JANMABHOOMI EXP", "up", "Sun", "ABD_dep", "09:07", 1, 1, None),
    ("22960", "INTERCITY EXP", "up", ALL, "ABD_dep", "09:45", 1, 1, None),
    ("94802", "NAMO BHARAT RAPID RAIL", "up", "Mon,Tue,Wed,Thu,Fri,Sat", "ABD_dep", "10:02", 1, 1, None),
    ("20685", "GIMB SBC SF EXP", "up", "Tue", "VG_dep", "12:43", 1, 0, None),
    ("12473", "SARVODAYA EXP", "up", "Sat", "VG_dep", "12:57", 1, 0, None),
    ("12475", "HAPA SVDK EXP", "up", "Tue", "VG_dep", "12:57", 1, 0, None),
    ("12477", "JAM SVDK EXP", "up", "Wed", "VG_dep", "12:57", 1, 0, None),
    ("16333", "VRL TVC EXP", "up", "Thu", "VG_dep", "14:07", 1, 0, None),
    ("16335", "GIMB NCJ EXP", "up", "Fri", "VG_dep", "14:07", 1, 0, None),
    ("16337", "OKHA ERS EXP", "up", "Mon,Sat", "VG_dep", "14:07", 1, 0, None),
    ("19120", "SOMNATH GNC EXP", "up", ALL, "ABD_dep", "14:57", 1, 1, None),
    ("12905", "SHALIMAR SF EXP", "up", "Wed,Thu", "VG_dep", "16:12", 1, 0, None),
    ("16734", "OKHA RMM EXP", "up", "Tue", "VG_dep", "16:12", 1, 0, None),
    ("22905", "OKHA SHM SF EXP", "up", "Sun", "VG_dep", "16:12", 1, 0, None),
    ("12949", "KAVIGURU EXP", "up", "Fri", "VG_dep", "16:12", 1, 0, None),
    ("22937", "RAJKOT REWA SF", "up", "Sun", "VG_dep", "16:57", 1, 0, None),
    ("22973", "GIMB PURI SUP", "up", "Wed", "VG_dep", "17:20", 1, 0, None),
    ("11463", "SMNH JBP EXP", "up", "Tue,Wed,Thu,Fri,Sun", "CLDY_arr", "17:48", 1, 0, None),
    ("11465", "SMNH JBP EXP", "up", "Mon,Sat", "CLDY_arr", "17:48", 1, 0, None),
    ("11087", "VERAVAL PUNE EXP", "up", "Sat", "VG_dep", "18:27", 1, 0, None),
    ("11091", "BHUJ PUNE SPL", "up", "Wed", "VG_dep", "18:27", 1, 0, None),
    ("19218", "SAURASHTRA JANTA", "up", ALL, "CLDY_arr", "19:25", 1, 0, None),
    ("22946", "SAURASHTRA MAIL", "up", ALL, "CLDY_arr", "19:42", 1, 0, 15),
    ("15635", "GUWAHATI EXPRES", "up", "Fri", "VG_dep", "20:12", 1, 0, 3),
    ("15667", "KAMAKHYA EXP", "up", "Sat", "VG_dep", "20:12", 1, 0, None),
    ("12941", "PARASNATH EXP", "up", "Tue", "VG_dep", "21:47", 1, 0, None),
    ("22964", "BVC BDTS SFAST", "up", "Sun", "VG_dep", "21:47", 1, 0, None),
    ("22969", "OKHA BSBS SF EXP", "up", "Thu", "VG_dep", "21:47", 1, 0, 20),
    ("20935", "GIMB INDB SF", "up", "Mon", "VG_dep", "21:47", 1, 0, None),
    ("14312", "BHUJ BE EXP", "up", "Tue,Wed,Fri", "CLDY_arr", "22:16", 1, 0, None),
    ("12972", "BVC BDTS SF EXP", "up", ALL, "VG_dep", "22:22", 1, 0, 10),
    ("22926", "SBT VANDE BHARAT", "up", "Mon,Wed,Thu,Fri,Sat,Sun", "ABD_dep", "22:42", 1, 1, None),
]

rows = []
for no, name, d, odays, ref, rt, dn, halt, delay in T:
    h, m = map(int, rt.split(":"))
    raw = h * 60 + m + OFF[(d, ref)]
    shift = (dn - 1) + raw // 1440           # days after origin day
    xdays = [DAYS[(DAYS.index(x.strip()) + shift) % 7] for x in odays.split(",")]
    xdays = [x for x in DAYS if x in xdays]  # keep Mon..Sun order
    cm = raw % 1440
    rows.append(dict(
        train_no=no, name=name, direction=d, halts_ABD=halt,
        crossing_time=f"{cm // 60:02d}:{cm % 60:02d}", crossing_min=cm,
        crossing_days=",".join(xdays), runs_per_week=len(xdays),
        ref_point=ref, ref_time=rt, day_no_at_ref=dn, origin_days=odays,
        avg_delay_min=delay, delay_source="trainspnrstatus_7day" if delay is not None else "",
    ))

df = pd.DataFrame(rows).sort_values("crossing_min").reset_index(drop=True)
df.to_csv("trains.csv", index=False)
print(len(df), "trains")
for day in DAYS:
    print(day, int(df.crossing_days.str.contains(day).sum()), "trains")
