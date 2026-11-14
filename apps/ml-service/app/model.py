"""Un único algoritmo global: HGB Poisson con NaN y categorías nativas."""
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from .data import CATEGORICAL,NUMERIC

PARAMETERS={'loss':'poisson','learning_rate':0.1,'max_iter':80,'max_leaf_nodes':31,
 'min_samples_leaf':30,'l2_regularization':1.0,'early_stopping':False,'random_state':42}

def build_model():
    encoder=ColumnTransformer([
      ('categories',OrdinalEncoder(handle_unknown='use_encoded_value',unknown_value=np.nan,dtype=np.float32),CATEGORICAL),
      ('numeric','passthrough',NUMERIC)])
    return Pipeline([('encoder',encoder),('regressor',HistGradientBoostingRegressor(
        categorical_features=[0,1],**PARAMETERS))])
