```
time duckdb clinvar.duckdb "select vrs_object->'location'->'sequenceReference'->>'refgetAccession' as refgetAccession, count(*) as ct from vrs_objects group by refgetAccession order by ct desc;"
┌─────────────────────────────────────┬────────┐
│           refgetAccession           │   ct   │
│               varchar               │ int64  │
├─────────────────────────────────────┼────────┤
│ SQ.pnAqCRBrTsUoBghSD1yp_jXWSmlbdh4g │ 277736 │
│ SQ.Ya6Rs7DHhDeg7YaOSg1EoNi3U_nQ9SvO │ 264664 │
│ SQ.dLZ15tNO1Ur0IcGjwc3Sdi_0A6Yf4zm7 │ 185427 │
│ SQ.2NkFm8HK88MqeNkCgj78KidCAXgnsfV1 │ 178315 │
│ SQ.IIB53T8CNeJJdUqzn9V_JnRtQadwWCbl │ 162652 │
│ SQ.Zu7h9AggXxhTaGVsy7h_EZSChSZGcmgX │ 161271 │
│ SQ.yC_0RBj3fgBlvgyAuycbzdubtLxq-rE0 │ 157296 │
│ SQ.aUiQCzCPZ2d0csHbMSbh2NzInhonSXwI │ 149626 │
│ SQ.F-LrLMe1SRpfUZHkQmvkVKFEGaoDeHul │ 144770 │
│ SQ.6wlJpONE3oNb4D69ULmEXhqyDZ4vwNfl │ 133783 │
│ SQ.0iKlIQk2oZLoeOG9P1riRU6hvL5Ux8TV │ 133664 │
│ SQ.KEO-4XBcm1cxeo_DIQ8_ofqGUkp4iZhI │ 132629 │
│ SQ.w0WZEvgJF0zf_P4yyTzjjv9oW1z61HHP │ 110993 │
│ SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB │ 110863 │
│ SQ.AsXvWL1-2i5U_buw6_niVIxD6zTbAuS6 │ 106336 │
│ SQ.HxuclGHh0XCDuF8x6yQrpHUBL7ZntAHc │ 103879 │
│ SQ.209Z7zJ-mFypBEWLk4rNC6S_OxY5p7bs │ 102426 │
│ SQ.eK4D2MosgK_ivBkgi6FVPg5UXs1bYESm │  95199 │
│ SQ.7B7SHsmchAR0dFcDCuSFjJAo7tX87krQ │  65390 │
│ SQ._0wi-qoDrvram155UmcSC-zA5ZK4fpLT │  62511 │
│                  ·                  │      · │
│                  ·                  │      · │
│                  ·                  │      · │
│ SQ.vKwE6pfbFaEu3UANcCrChyx2dDjuZgdM │      1 │
│ SQ.pHJyelegSnjjyE9PLP2EAoYC88_YeBHJ │      1 │
│ SQ.m_aJUmHF75It1WUbGw_qmpakb17e3s3A │      1 │
│ SQ.-dynXb5YKfLPND_rBbbxrUMLSCYTQKp6 │      1 │
│ SQ.JJ4J3VSuBl1JLXGlaj1MfZi1eQ1DnpzS │      1 │
│ SQ.fbjuINAC6ATwDlVj9HnA1KPKscDmijI0 │      1 │
│ SQ.mziNo-HVpqT9F5hwqFeNaIJ6nM9yxKKl │      1 │
│ SQ.RrUpibofU4xvBk4uLQoR5PuoVOAUi8nc │      1 │
│ SQ.5gMuKsdp5K-Br-qPuAHHf7facD7govuZ │      1 │
│ SQ.nNDZTrbR1bifTFr29OuFRaG3ImyDnzxP │      1 │
│ SQ.HTUkFF3UuG0zMdlAsMCOiFvVcWCIlM4e │      1 │
│ SQ.6I7IeLrvLVcxTL9S_46iA7Dfr9PgDi8D │      1 │
│ SQ.JODvILIOTwbJcvKwnRFKryJJwLe_cWPB │      1 │
│ SQ.SgOraPkndDzGu6HzmC4nre-YV4KCx7VO │      1 │
│ SQ.iQjJYXf_974vatLpjP9lyqmLEeIaUyZ9 │      1 │
│ SQ.EX6Y0Xw5pDSZHQY2WYHZYDZKyEAOvQMF │      1 │
│ SQ.nxDyzWEG2S19-ew36tkvIc5SA3jLLohw │      1 │
│ SQ.1dag3me2zw1Tx6LCHG55AeqTf4e81d3f │      1 │
│ SQ.AFwKWQ1DJrQTfkXsrS-OwJOL7l2lICKq │      1 │
│ SQ.u4LpdUe2hzZOZdMG9rQX4XyjCxsR_ZjF │      1 │
├─────────────────────────────────────┴────────┤
│ 166 rows (40 shown)                2 columns │
└──────────────────────────────────────────────┘
duckdb clinvar.duckdb   2.81s user 0.31s system 927% cpu 0.336 total
```


```
$ time duckdb clinvar.duckdb "select vrs_object->>'type' as object_type, count(*) as ct from vrs_objects group by object_type ;"
┌──────────────────┬─────────┐
│   object_type    │   ct    │
│     varchar      │  int64  │
├──────────────────┼─────────┤
│ CopyNumberChange │    1848 │
│ CopyNumberCount  │    1111 │
│ Allele           │ 2990635 │
└──────────────────┴─────────┘
duckdb clinvar.duckdb   1.29s user 0.22s system 317% cpu 0.475 total
```
