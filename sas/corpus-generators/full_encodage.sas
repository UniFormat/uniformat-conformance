/* encodages exotiques (SAS complet seulement) */
/* Genere par corpus/gen/build_programs.py : ne pas modifier a la main. */
options nodate nonumber linesize=200 pagesize=32000;
libname o "/work/files_sas_small/encodage";
data o.encodage_sjis_no(compress=no encoding='shift-jis');
  length c $20; c="日本語"; output;
run;
title1 "@@@ encodage_sjis_no contents";
proc contents data=o.encodage_sjis_no; run;
title1 "@@@ encodage_sjis_no print";
proc print data=o.encodage_sjis_no; run;
title1;
data _null_; file "/work/files_sas_small/encodage/encodage_sjis_no.csv" lrecl=1000000;
  put "c";
run;
data _null_; set o.encodage_sjis_no; file "/work/files_sas_small/encodage/encodage_sjis_no.csv" mod dlm="," lrecl=1000000;
  put c :$quote22.;
run;
