#!/bin/python 

import os
import sys

project_path, x = os.path.split(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(project_path)

import tensorflow as tf
from keras.optimizers import Adam
from keras.callbacks import ModelCheckpoint, EarlyStopping, CSVLogger

from bnn.model import create_model, encoder_min_input_size
from bnn.loss_equations import bayesian_categorical_crossentropy
from bnn.util import isAWS, upload_s3
from bnn.data import test_train_data

class Config(object):
	def __init__(self, encoder, dataset, batch_size, epochs, monte_carlo_simulations):
		self.encoder = encoder
		self.dataset = dataset
		self.epochs = epochs
		self.batch_size = batch_size
		self.monte_carlo_simulations = monte_carlo_simulations

	def info(self):
		print("encoder:", self.encoder)
		print("batch_size:", self.batch_size)
		print("epochs:", self.epochs)
		print("dataset:", self.dataset)
		print("monte_carlo_simulations:", self.monte_carlo_simulations)

	def model_file(self):
		return "model_{}_{}_{}_{}_{}.ckpt".format(self.encoder, self.dataset, self.batch_size, self.epochs, self.monte_carlo_simulations)

	def csv_log_file(self):
		return "model_training_logs_{}_{}_{}_{}_{}.csv".format(self.encoder, self.dataset, self.batch_size, self.epochs, self.monte_carlo_simulations)

flags = tf.app.flags
FLAGS = flags.FLAGS

flags.DEFINE_string('dataset', 'cifar10', 'The dataset to train the model on.')
flags.DEFINE_string('encoder', 'resnet50', 'The encoder model to train from.')
flags.DEFINE_integer('epochs', 1, 'Number of training examples.')
flags.DEFINE_integer('monte_carlo_simulations', 100, 'The number of monte carlo simulations to run for the aleatoric categorical crossentroy loss function.')
flags.DEFINE_integer('batch_size', 32, 'The batch size for the generator')
flags.DEFINE_boolean('debug', False, 'If this is for debugging the model/training process or not.')
flags.DEFINE_integer('verbose', 0, 'Whether to use verbose logging when constructing the data object.')
flags.DEFINE_boolean('stop', True, 'Stop aws instance after finished running.')
# flags.DEFINE_float('min_delta', 0.1, 'Early stopping minimum change value.')
# flags.DEFINE_integer('patience', 10, 'Early stopping epochs patience to wait before stopping.')


def main(_):
	config = Config(FLAGS.encoder, FLAGS.dataset, FLAGS.batch_size, FLAGS.epochs, FLAGS.monte_carlo_simulations)
	config.info()

	min_image_size = encoder_min_input_size(FLAGS.encoder)
	
	((x_train, y_train), (x_test, y_test)) = test_train_data(FLAGS.dataset, min_image_size, FLAGS.debug)

	min_image_size = list(min_image_size)
	min_image_size.append(3)
	num_classes = y_train.shape[-1]

	model = create_model(min_image_size, num_classes)

	if FLAGS.debug:
		print(model.summary())
		callbacks = None
	else:
		callbacks = [
			ModelCheckpoint(config.model_file(), verbose=FLAGS.verbose, save_best_only=True),
			CSVLogger(config.csv_log_file())
			# EarlyStopping(min_delta=min_delta, patience=patience, verbose=1)
		]

	model.compile(
		optimizer=Adam(lr=1e-3), 
		loss={'logits_variance': bayesian_categorical_crossentropy(FLAGS.monte_carlo_simulations, num_classes)},
		metrics={'softmax_output': 'categorical_accuracy'})

	model.fit(x_train, y_train, 
		callbacks=callbacks,
		verbose=FLAGS.verbose,
		epochs=FLAGS.epochs,
		batch_size=FLAGS.batch_size,
		validation_data=(x_test, y_test))

	if isAWS():
		upload_s3(config.model_file())
		upload_s3(config.csv_log_file())

	if isAWS() and FLAGS.stop:
		stop_instance()


if __name__ == '__main__':
	tf.app.run()
