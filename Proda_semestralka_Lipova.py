# -*- coding: utf-8 -*-

import arcpy
import os

# Povolit přepisování výstupů
arcpy.env.overwriteOutput = True
sit = arcpy.GetParameterAsText(0)          # ND_walking
skoly = arcpy.GetParameterAsText(1)        # bodová vrstva škol
obyvatele = arcpy.GetParameterAsText(2)    # obyv20251101
out_gdb = arcpy.GetParameterAsText(3)      # výstupní geodatabáze
spadove_oblasti = arcpy.GetParameterAsText(4)      # polygonová vrstva spádových oblastí
casy_dostupnosti = arcpy.GetParameterAsText(5)     # např. "5;10;15"
out_excel = arcpy.GetParameterAsText(6)            # volitelný výstupní Excel soubor
# ------------------------------------------------------------
# PŘEVOD ZADANÝCH ČASŮ NA SEZNAM
# ------------------------------------------------------------

# Uživatel může napsat např. "5;10;15" nebo "5 10 15"
casy_text = casy_dostupnosti.replace(";", " ").replace(",", " ")

casy = []

try:
    for hodnota in casy_text.split():
        casy.append(float(hodnota))
except ValueError:
    arcpy.AddError("Časy dostupnosti musí být čísla oddělená středníkem, čárkou nebo mezerou. Například: 5;10;15")
    raise Exception("Neplatný formát časů dostupnosti.")
if len(casy) == 0:
    arcpy.AddError("Nebyl zadán žádný čas dostupnosti. Zadejte například 5;10.")
    raise Exception("Chybí časy dostupnosti.")

arcpy.AddMessage(f"Použité časy dostupnosti v minutách: {casy}")    
arcpy.AddMessage("Spouštím nástroj pro dostupnost škol...")
arcpy.AddMessage("----------------------------------------")

arcpy.AddMessage(f"Síť: {sit}")
arcpy.AddMessage(f"Školy: {skoly}")
arcpy.AddMessage(f"Obyvatelstvo: {obyvatele}")
arcpy.AddMessage(f"Výstupní geodatabáze: {out_gdb}")

# ------------------------------------------------------------
# 3) KONTROLA POČTU PRVKŮ
# ------------------------------------------------------------

pocet_skol = int(arcpy.management.GetCount(skoly)[0])
pocet_obyv = int(arcpy.management.GetCount(obyvatele)[0])

arcpy.AddMessage("----------------------------------------")
arcpy.AddMessage(f"Počet škol: {pocet_skol}")
arcpy.AddMessage(f"Počet obyvatelských bodů: {pocet_obyv}")

# ------------------------------------------------------------
# 4) TEST, ŽE EXISTUJE VÝSTUPNÍ GEODATABÁZE
# ------------------------------------------------------------

if arcpy.Exists(out_gdb):
    arcpy.AddMessage("Výstupní geodatabáze existuje.")
else:
    arcpy.AddError("Výstupní geodatabáze neexistuje.")
    raise Exception("Neplatná výstupní geodatabáze.")

# ------------------------------------------------------------
# 5) VYTVOŘENÍ SERVICE AREA VRSTVY
# ------------------------------------------------------------

arcpy.AddMessage("----------------------------------------")
arcpy.AddMessage("Vytvářím Service Area analýzu pro školy...")

sa_result = arcpy.na.MakeServiceAreaAnalysisLayer(
    network_data_source=sit,
    layer_name="SA_skoly_casova_dostupnost",
    travel_direction="FROM_FACILITIES",
    cutoffs=casy,
    output_type="POLYGONS",
    polygon_detail="STANDARD",
    geometry_at_overlaps="OVERLAP",
    geometry_at_cutoffs="DISKS"
)

sa_layer = sa_result.getOutput(0)

arcpy.AddMessage("Service Area vrstva byla vytvořena.")

# ------------------------------------------------------------
# 6) PŘIDÁNÍ ŠKOL JAKO FACILITIES
# ------------------------------------------------------------

arcpy.AddMessage("Přidávám školy do Service Area analýzy...")

# Zjištění názvů podvrstev uvnitř Service Area vrstvy
sublayers = arcpy.na.GetNAClassNames(sa_layer)

facilities_layer = sublayers["Facilities"]
polygons_layer = sublayers["SAPolygons"]

# Nastavení mapování polí
field_mappings = arcpy.na.NAClassFieldMappings(sa_layer, facilities_layer)

# Zjistíme, jaká pole má vrstva škol
pole_skoly = [field.name for field in arcpy.ListFields(skoly)]

# Pro finální porovnání potřebujeme, aby Service Area měla jako Name IČO školy
if "ico" in pole_skoly:
    field_mappings["Name"].mappedFieldName = "ico"
    arcpy.AddMessage("Jako identifikátor školy ve Service Area používám pole: ico")

elif "IČO" in pole_skoly:
    field_mappings["Name"].mappedFieldName = "IČO"
    arcpy.AddMessage("Jako identifikátor školy ve Service Area používám pole: IČO")

else:
    arcpy.AddError("Ve vrstvě škol nebylo nalezeno pole ico ani IČO.")
    raise Exception("Chybí pole ico/IČO ve vrstvě škol.")

# Přidání škol jako výchozích bodů dostupnosti
arcpy.na.AddLocations(
    in_network_analysis_layer=sa_layer,
    sub_layer=facilities_layer,
    in_table=skoly,
    field_mappings=field_mappings,
    search_tolerance="500 Meters",
    append="CLEAR",
    snap_to_position_along_network="SNAP"
)

arcpy.AddMessage("Školy byly přidány jako Facilities.")

# ------------------------------------------------------------
# VYTVOŘENÍ PRACOVNÍ VRSTVY OBYVATEL A POLE DETI_6_14
# ------------------------------------------------------------

arcpy.AddMessage("----------------------------------------")
arcpy.AddMessage("Připravuji obyvatelská data a počítám děti 6–14 let...")

obyv_pracovni = os.path.join(out_gdb, "obyv_pracovni_deti_6_14")

arcpy.management.CopyFeatures(
    in_features=obyvatele,
    out_feature_class=obyv_pracovni
)
# Kontrola, že obyvatelská vrstva obsahuje potřebná věková pole
povinna_pole_obyv = ["sum_6", "sum_7", "sum_8", "sum_9", "sum_10_14"]
pole_obyv = [f.name for f in arcpy.ListFields(obyv_pracovni)]

for pole in povinna_pole_obyv:
    if pole not in pole_obyv:
        arcpy.AddError(f"V obyvatelské vrstvě chybí povinné pole: {pole}")
        raise Exception(f"Chybí pole {pole}")

# Přidání nového pole pro děti 6–14
if "deti_6_14" not in [f.name for f in arcpy.ListFields(obyv_pracovni)]:
    arcpy.management.AddField(
        in_table=obyv_pracovni,
        field_name="deti_6_14",
        field_type="LONG"
    )

# Výpočet dětí 6–14
arcpy.management.CalculateField(
    in_table=obyv_pracovni,
    field="deti_6_14",
    expression="(!sum_6! or 0) + (!sum_7! or 0) + (!sum_8! or 0) + (!sum_9! or 0) + (!sum_10_14! or 0)",
    expression_type="PYTHON3"
)

arcpy.AddMessage("Pole deti_6_14 bylo vypočteno.")

# ------------------------------------------------------------
# 7) VÝPOČET A ULOŽENÍ SERVICE AREA POLYGONŮ
# ------------------------------------------------------------

arcpy.AddMessage("Počítám Service Area polygony...")

arcpy.na.Solve(sa_layer)

arcpy.AddMessage("Service Area výpočet doběhl.")

casy_suffix = "_".join([
    str(int(c)) if float(c).is_integer() else str(c).replace(".", "_")
    for c in casy
])
# Název výstupní vrstvy v geodatabázi
out_service_area = os.path.join(out_gdb, f"SA_skoly_{casy_suffix}_min")

# Uložení polygonů do geodatabáze
arcpy.management.CopyFeatures(
    in_features=f"{sa_layer}\\{polygons_layer}",
    out_feature_class=out_service_area
)
# ------------------------------------------------------------
# ÚPRAVA SERVICE AREA - VYTVOŘENÍ ČISTÉHO IČO Z POLE NAME
# ------------------------------------------------------------

arcpy.AddMessage("----------------------------------------")
arcpy.AddMessage("Vytvářím pole ico_sa v Service Area polygonech...")

if "ico_sa" not in [f.name for f in arcpy.ListFields(out_service_area)]:
    arcpy.management.AddField(
        in_table=out_service_area,
        field_name="ico_sa",
        field_type="TEXT",
        field_length=30
    )

arcpy.management.CalculateField(
    in_table=out_service_area,
    field="ico_sa",
    expression="str(!Name!).split(':')[0].strip()",
    expression_type="PYTHON3"
)

arcpy.AddMessage("Pole ico_sa bylo vytvořeno.")
# ------------------------------------------------------------
# FINÁLNÍ TABULKA: SPÁD VS. ČASOVÁ DOSTUPNOST
# ------------------------------------------------------------

arcpy.AddMessage("----------------------------------------")
arcpy.AddMessage("Vytvářím finální tabulku po školách...")

# Pomocná funkce: najde pole podle možných názvů
def najdi_pole(vrstva, kandidati):
    pole = {f.name.lower(): f.name for f in arcpy.ListFields(vrstva)}
    for kandidat in kandidati:
        if kandidat.lower() in pole:
            return pole[kandidat.lower()]
    return None

# Pomocná funkce: převede hodnotu na čistý text
def hodnota_na_text(hodnota):
    if hodnota is None:
        return ""
    if isinstance(hodnota, float) and hodnota.is_integer():
        return str(int(hodnota))
    return str(hodnota).strip()

# Pomocná funkce: z času udělá bezpečný název pole
def cas_do_pole(cas):
    if float(cas).is_integer():
        return str(int(cas))
    return str(cas).replace(".", "_")

# Pomocná funkce: sečte děti ve vybrané vrstvě bodů
def secti_deti(vrstva_bodu, pole_deti):
    soucet = 0
    with arcpy.da.SearchCursor(vrstva_bodu, [pole_deti]) as cursor:
        for row in cursor:
            if row[0] is not None:
                soucet += row[0]
    return soucet

# Najdeme IČO a název školy ve spádových oblastech
spad_ico_field = najdi_pole(spadove_oblasti, ["ico", "IČO", "ICO"])
spad_nazev_field = najdi_pole(spadove_oblasti, ["KRATKY_NAZ", "DLOUHY_NAZ", "plnyNazev", "nazev"])

if spad_ico_field is None:
    arcpy.AddError("Ve spádových oblastech nebylo nalezeno pole ico/IČO.")
    raise Exception("Chybí pole ico/IČO ve spádových oblastech.")

# Výstupní tabulka
out_final_table = os.path.join(out_gdb, "finalni_tabulka_skoly")

if arcpy.Exists(out_final_table):
    arcpy.management.Delete(out_final_table)

arcpy.management.CreateTable(out_gdb, "finalni_tabulka_skoly")

# Základní pole
arcpy.management.AddField(out_final_table, "ico", "TEXT", field_length=30)
arcpy.management.AddField(out_final_table, "skola", "TEXT", field_length=255)
arcpy.management.AddField(out_final_table, "deti_spad", "LONG")

# Dynamická pole podle časů, např. dost_5, ve_spadu_5, mimo_spad_5
for cas in casy:
    suffix = cas_do_pole(cas)
    arcpy.management.AddField(out_final_table, f"dost_{suffix}", "LONG")
    arcpy.management.AddField(out_final_table, f"ve_spadu_{suffix}", "LONG")
    arcpy.management.AddField(out_final_table, f"mimo_spad_{suffix}", "LONG")

for tmp in ["spad_layer_final", "sa_layer_final", "obyv_layer_final"]:
    if arcpy.Exists(tmp):
        arcpy.management.Delete(tmp)
# Vytvoření dočasných vrstev pro výběry
spad_layer = "spad_layer_final"
sa_layer_final = "sa_layer_final"
obyv_layer = "obyv_layer_final"

arcpy.management.MakeFeatureLayer(spadove_oblasti, spad_layer)
arcpy.management.MakeFeatureLayer(out_service_area, sa_layer_final)
arcpy.management.MakeFeatureLayer(obyv_pracovni, obyv_layer)

spad_oid_field = arcpy.Describe(spadove_oblasti).OIDFieldName

# Pole pro zápis do finální tabulky
insert_fields = ["ico", "skola", "deti_spad"]

for cas in casy:
    suffix = cas_do_pole(cas)
    insert_fields.append(f"dost_{suffix}")
    insert_fields.append(f"ve_spadu_{suffix}")
    insert_fields.append(f"mimo_spad_{suffix}")

# Pole pro čtení spádových oblastí
read_fields = [spad_oid_field, spad_ico_field]

if spad_nazev_field is not None:
    read_fields.append(spad_nazev_field)

# Každá spádová oblast / škola = jeden řádek finální tabulky
with arcpy.da.InsertCursor(out_final_table, insert_fields) as insert_cursor:

    with arcpy.da.SearchCursor(spadove_oblasti, read_fields) as spad_cursor:

        for spad_row in spad_cursor:

            spad_oid = spad_row[0]
            ico = hodnota_na_text(spad_row[1])

            if spad_nazev_field is not None:
                nazev_skoly = hodnota_na_text(spad_row[2])
            else:
                nazev_skoly = ""

            arcpy.AddMessage(f"Zpracovávám školu: {ico} {nazev_skoly}")

            # 1) Vybereme jednu oficiální spádovou oblast
            where_spad = f"{arcpy.AddFieldDelimiters(spadove_oblasti, spad_oid_field)} = {spad_oid}"

            arcpy.management.SelectLayerByAttribute(
                in_layer_or_view=spad_layer,
                selection_type="NEW_SELECTION",
                where_clause=where_spad
            )

            # 2) Spočítáme děti v celé oficiální spádové oblasti
            arcpy.management.SelectLayerByLocation(
                in_layer=obyv_layer,
                overlap_type="INTERSECT",
                select_features=spad_layer,
                selection_type="NEW_SELECTION"
            )

            deti_spad = secti_deti(obyv_layer, "deti_6_14")

            hodnoty_radku = [ico, nazev_skoly, deti_spad]

            # 3) Pro každý čas spočítáme:
            #    A) všechny děti v dostupnosti školy
            #    B) kolik z nich je zároveň v oficiální spádové oblasti
            #    C) kolik je mimo oficiální spád
            for cas in casy:

                suffix = cas_do_pole(cas)
                ico_sql = ico.replace("'", "''")

                
                where_sa = (
                    f"{arcpy.AddFieldDelimiters(out_service_area, 'ico_sa')} = '{ico_sql}' "
                    f"AND {arcpy.AddFieldDelimiters(out_service_area, 'ToBreak')} = {float(cas)}")

                arcpy.management.SelectLayerByAttribute(
                    in_layer_or_view=sa_layer_final,
                    selection_type="NEW_SELECTION",
                    where_clause=where_sa
                )

                pocet_sa_polygonu = int(arcpy.management.GetCount(sa_layer_final)[0])

                if pocet_sa_polygonu == 0:
                    arcpy.AddWarning(f"Pro školu {ico} a čas {cas} min nebyl nalezen Service Area polygon.")
                    deti_dostupnost = 0
                    deti_ve_spadu = 0
                    deti_mimo_spad = 0

                else:
                    # A) všechny děti v časové dostupnosti školy
                    arcpy.management.SelectLayerByLocation(
                        in_layer=obyv_layer,
                        overlap_type="INTERSECT",
                        select_features=sa_layer_final,
                        selection_type="NEW_SELECTION"
                    )

                    deti_dostupnost = secti_deti(obyv_layer, "deti_6_14")

                    # B) z těchto dětí necháme jen ty, které jsou zároveň ve spádové oblasti školy
                    arcpy.management.SelectLayerByLocation(
                        in_layer=obyv_layer,
                        overlap_type="INTERSECT",
                        select_features=spad_layer,
                        selection_type="SUBSET_SELECTION"
                    )

                    deti_ve_spadu = secti_deti(obyv_layer, "deti_6_14")

                    # C) děti v dostupnosti, ale mimo oficiální spád
                    deti_mimo_spad = deti_dostupnost - deti_ve_spadu

                hodnoty_radku.append(deti_dostupnost)
                hodnoty_radku.append(deti_ve_spadu)
                hodnoty_radku.append(deti_mimo_spad)

            insert_cursor.insertRow(hodnoty_radku)

# Vyčištění výběrů
arcpy.management.SelectLayerByAttribute(spad_layer, "CLEAR_SELECTION")
arcpy.management.SelectLayerByAttribute(sa_layer_final, "CLEAR_SELECTION")
arcpy.management.SelectLayerByAttribute(obyv_layer, "CLEAR_SELECTION")

arcpy.AddMessage("Finální tabulka byla vytvořena.")
arcpy.AddMessage(f"Finální tabulka: {out_final_table}")
# ------------------------------------------------------------
# 8) SOUČET DĚTÍ 6–14 V SERVICE AREA POLYGONECH
# ------------------------------------------------------------

arcpy.AddMessage("----------------------------------------")
arcpy.AddMessage("Počítám děti 6–14 let v dostupnostních oblastech...")

# Název výstupu po nástroji Summarize Within
out_sa_deti = os.path.join(out_gdb, f"SA_skoly_{casy_suffix}_min_deti_6_14")

# Summarize Within:
# in_polygons = service area polygony
# in_sum_features = obyvatelské body s vypočteným polem deti_6_14
arcpy.analysis.SummarizeWithin(
    in_polygons=out_service_area,
    in_sum_features=obyv_pracovni,
    out_feature_class=out_sa_deti,
    keep_all_polygons="KEEP_ALL",
    sum_fields=[
        ["deti_6_14", "SUM"]
    ],
    sum_shape="NO_SHAPE_SUM"
)

arcpy.AddMessage("Součet dětí 6–14 let v dostupnostních oblastech byl dokončen.")
arcpy.AddMessage(f"Výstup s dětmi: {out_sa_deti}")

# ------------------------------------------------------------
# EXPORT FINÁLNÍ TABULKY DO EXCELU
# ------------------------------------------------------------

arcpy.AddMessage("----------------------------------------")
arcpy.AddMessage("Exportuji finální tabulku do Excelu...")

arcpy.AddMessage(f"Uživatelem zadaná cesta pro Excel: {out_excel}")

# Pokud uživatel nezadá vlastní cestu, Excel se uloží vedle geodatabáze
if not out_excel:
    out_folder = os.path.dirname(out_gdb)
    out_excel = os.path.join(out_folder, "finalni_tabulka_skoly.xlsx")

# Pokud uživatel zadá cestu bez přípony, doplní se .xlsx
if not out_excel.lower().endswith(".xlsx"):
    out_excel = out_excel + ".xlsx"

# Kontrola, že výstupní složka existuje
out_excel_folder = os.path.dirname(out_excel)

if not os.path.exists(out_excel_folder):
    arcpy.AddError(f"Složka pro uložení Excelu neexistuje: {out_excel_folder}")
    raise Exception("Neplatná složka pro výstupní Excel.")

# Pokud už Excel existuje, smažeme ho, aby export nespadl
if os.path.exists(out_excel):
    try:
        os.remove(out_excel)
    except PermissionError:
        arcpy.AddError("Výstupní Excel soubor je pravděpodobně otevřený. Zavřete ho a spusťte nástroj znovu.")
        raise Exception("Excel soubor je otevřený.")

arcpy.conversion.TableToExcel(
    Input_Table=out_final_table,
    Output_Excel_File=out_excel
)

arcpy.AddMessage(f"Finální tabulka byla exportována do Excelu: {out_excel}")
arcpy.SetParameterAsText(6, out_excel)

# ------------------------------------------------------------
# PŘIDÁNÍ VÝSTUPŮ DO AKTUÁLNÍ MAPY / PROJEKTU
# ------------------------------------------------------------

try:
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    mapa = aprx.activeMap

    if mapa is not None:
        mapa.addDataFromPath(out_sa_deti)
        mapa.addDataFromPath(out_final_table)
        arcpy.AddMessage("Finální vrstva a finální tabulka byly přidány do projektu.")
    else:
        arcpy.AddWarning("Nepodařilo se najít aktivní mapu. Výstupy jsou uložené v geodatabázi.")

except Exception as e:
    arcpy.AddWarning(f"Výstupy se nepodařilo automaticky přidat do projektu: {e}")

arcpy.AddMessage("----------------------------------------")
arcpy.AddMessage("Service Area polygony byly uloženy.")
arcpy.AddMessage(f"Výstup: {out_service_area}")
