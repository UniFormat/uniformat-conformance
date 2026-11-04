/* index simple (SAS complet seulement) */
/* Genere par corpus/gen/build_programs.py : ne pas modifier a la main. */
options nodate nonumber linesize=200 pagesize=32000;
libname o "/work/files_sas_small/index";
libname b "/work/files_sas_small/base";
data o.index_n100_ix_no(compress=no); set b.base_n100_mix_no; run;
proc datasets lib=o nolist; modify index_n100_ix_no; index create ix=(i); quit;
title1 "@@@ index_n100_ix_no contents";
proc contents data=o.index_n100_ix_no; run;
title1 "@@@ index_n100_ix_no print";
proc print data=o.index_n100_ix_no; run;
title1;
data _null_; file "/work/files_sas_small/index/index_n100_ix_no.csv" lrecl=1000000;
  put "i,x,c";
run;
data _null_; set o.index_n100_ix_no; file "/work/files_sas_small/index/index_n100_ix_no.csv" mod dlm="," lrecl=1000000;
  put i :best32. x :best32. c :$quote7.;
run;
