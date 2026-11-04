/* catalogue de formats (SAS complet seulement) */
/* Genere par corpus/gen/build_programs.py : ne pas modifier a la main. */
options nodate nonumber linesize=200 pagesize=32000;
libname o "/work/files_sas_small/catalogue";
libname b "/work/files_sas_small/base";
libname fmtlib "/work/files_sas_small/catalogue";
proc format library=fmtlib; value ff 1='un' 2='deux' 3-high='plus' other='autre'; invalue inf 'a'=1 'b'=2; picture pp low-high='000.00'; run;
proc format library=fmtlib cntlout=o.catalogue_cntlout; run;
data o.catalogue_fmtuser_no(compress=no); set b.base_n100_mix_no; format i ff.; run;
title1 "@@@ catalogue_fmtuser_no contents";
proc contents data=o.catalogue_fmtuser_no; run;
title1 "@@@ catalogue_fmtuser_no print";
proc print data=o.catalogue_fmtuser_no; run;
title1;
title1 "@@@ catalogue_fmtlib print";
proc format library=fmtlib fmtlib; run;
title1;
data _null_; file "/work/files_sas_small/catalogue/catalogue_fmtuser_no.csv" lrecl=1000000;
  put "i,x,c";
run;
data _null_; set o.catalogue_fmtuser_no; file "/work/files_sas_small/catalogue/catalogue_fmtuser_no.csv" mod dlm="," lrecl=1000000;
  put i :best32. x :best32. c :$quote7.;
run;
