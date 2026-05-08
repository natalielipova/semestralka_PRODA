# semestralka_PRODA
Odevzdaní semestrální práce PRODA 2026. Python Script Tool pro ArcGIS Pro – výpočet časové dostupnosti základních škol.

## Popis

Skript automatizuje výpočet časové dostupnosti základních škol pomocí síťové analýzy v ArcGIS Pro. Pracuje s bodovou vrstvou škol, pěším síťovým datasetem, obyvatelskými daty a polygonovou vrstvou spádových oblastí škol.

## Co skript umí

- vytvoří časové dostupnostní oblasti kolem základních škol,
- umožňuje zadat vlastní časové limity, například `5;10` nebo `5;10;15` minut,
- vypočítá počet dětí ve věku 6–14 let,
- spočítá počet dětí ve spádové oblasti školy,
- spočítá počet dětí dostupných v jednotlivých časových limitech,
- určí, kolik dostupných dětí leží uvnitř a mimo oficiální spádovou oblast,
- vytvoří výslednou tabulku po školách,
- exportuje výslednou tabulku do formátu `.xlsx`,
- přidá výstupní vrstvu a tabulku zpět do projektu ArcGIS Pro.

## Vstupy

- síťový dataset pro pěší dostupnost,
- bodová vrstva základních škol,
- bodová vrstva obyvatelstva,
- polygonová vrstva spádových oblastí,
- výstupní geodatabáze,
- časové limity dostupnosti,
- cesta pro export výsledné Excel tabulky.

## Výstupy

- polygonová vrstva dostupnostních oblastí,
- finální tabulka s výsledky za jednotlivé školy,
- exportovaná Excel tabulka.

