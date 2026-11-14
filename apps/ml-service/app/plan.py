"""Plan temporal determinista por corte; sin selección a partir del holdout."""
from datetime import date,timedelta

def for_cutoff(cutoff):
    cutoff=date.fromisoformat(str(cutoff))
    if cutoff<date(2014,12,31):raise ValueError('Corte anterior al bootstrap')
    evaluation_end=cutoff-timedelta(days=7)
    evaluation_start=evaluation_end-timedelta(days=13)
    validation_end=evaluation_start-timedelta(days=8)
    validation_start=validation_end-timedelta(days=20)
    fit=validation_start-timedelta(days=1)
    return {'cutoff':cutoff,'fit_date':fit,'version':'sales-pit-v2','contract':'gold-features-v2.json',
      'splits':{'train':(date(2013,1,7),fit-timedelta(days=1),fit),
      'validation':(validation_start,validation_end,evaluation_start-timedelta(days=1)),
      'evaluation':(evaluation_start,evaluation_end,cutoff)}}
