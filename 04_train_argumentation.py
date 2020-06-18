# %%
import os, random, time
import numpy as np
import pandas as pd
import tensorflow as tf
from matplotlib import pyplot as plt
from sklearn.model_selection import train_test_split
from tensorflow.keras import layers, models, losses, optimizers, callbacks
from tensorflow.keras.applications import Xception
from tensorflow.keras.preprocessing.image import ImageDataGenerator

import wandb
from wandb.keras import WandbCallback
print("Package Loaded!")
# %%
# For Efficiency
gpus = tf.config.experimental.list_physical_devices('GPU')
if gpus:
    try:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        logical_gpus = tf.config.experimental.list_logical_devices('GPU')
        print(len(gpus), "Physical GPUs,", len(logical_gpus), "Logical GPUs")
    except RuntimeError as e:
        print(e)
# %%
ROOT = '/data/jerry/private/data'

TR_CSV_PATH = os.path.join(ROOT, "new_train.csv")
TE_CSV_PATH = os.path.join(ROOT, "new_test.csv")

TR_IMG_PATH = os.path.join(ROOT, 'jpeg', 'train')
TE_IMG_PATH = os.path.join(ROOT, 'jpeg', 'test')

SIZE = 224
BATCH_SIZE = 1024
SEED = 777
EPOCHS=10

random.seed(SEED)
np.random.seed(SEED)
tf.random.set_seed(SEED)

date = time.ctime()[:-14].replace(' ', '_')
wandb.init(project="kaggle_melanoma", name=date)
# %%
tr_csv = pd.read_csv(TR_CSV_PATH)
tr_csv['target']= tr_csv['target'].astype("str")
tr_csv, val_csv = train_test_split(tr_csv, test_size = 0.05, random_state=SEED, shuffle=True)
print(tr_csv.head(5))
print(val_csv.head(5))

te_csv = pd.read_csv(TE_CSV_PATH)
print(te_csv.head(5))

# %%

train_image_generator = ImageDataGenerator(rescale=1./255, 
                                            rotation_range=180, 
                                            width_shift_range = [-0.1, 0.1], 
                                            height_shift_range = [-0.1, 0.1], 
                                            shear_range = 0.1, 
                                            zoom_range = 0.25, 
                                            horizontal_flip = True, 
                                            vertical_flip = True) # Generator for our training data
val_image_generator = ImageDataGenerator(rescale=1./255)
test_image_generator = ImageDataGenerator(rescale=1./255) # Generator for our validation data


train_generator = train_image_generator.flow_from_dataframe(tr_csv, directory=TR_IMG_PATH, \
                                                                x_col='image_name', y_col='target',\
                                                                target_size=(SIZE, SIZE), class_mode='binary',\
                                                                batch_size=BATCH_SIZE, seed=SEED)

val_generator = val_image_generator.flow_from_dataframe(val_csv, directory=TR_IMG_PATH, \
								x_col='image_name', y_col='target',\
                                                                target_size=(SIZE, SIZE), class_mode='binary',\
                                                                batch_size=BATCH_SIZE, seed=SEED)

test_generator = test_image_generator.flow_from_dataframe(te_csv, directory=TE_IMG_PATH,\
                                                                x_col='image_name', y_col=None,\
                                                                class_mode=None, target_size=(SIZE, SIZE),\
                                                                batch_size=BATCH_SIZE, seed=SEED)

reducelr = callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.95, patience=4, verbose=1)
earlystop = callbacks.EarlyStopping(monitor='val_loss', patience=7, restore_best_weights=True)
wandb_callback = WandbCallback(input_type='image', labels=[0,1], save_weights_only=True)

# %%
strategy = tf.distribute.MirroredStrategy()
with strategy.scope():
    base_model = Xception(weights="imagenet", include_top=False, pooling='avg')
    base_model.summary()

    out = layers.Dense(1, activation="sigmoid")(base_model.output)
    model = models.Model(base_model.input, out)
    model.compile(loss = 'binary_crossentropy', optimizer='adam', metrics=['acc'])
# %%
model.fit(train_generator, \
            epochs=EPOCHS, \
            validation_data=val_generator, \
            callbacks = [reducelr, earlystop, wandb_callback], \
            workers=24,
            max_queue_size=32)

# %%
# %%
result = model.predict(test_generator, verbose=1)
# %%
SP_CSV_PATH = os.path.join(ROOT, "sample_submission.csv")
sample_csv = pd.read_csv(SP_CSV_PATH)
sample_csv['target'] = result
sample_csv.to_csv("./submission.csv", index=False)

