"""Functions for reading and initializing fmri data."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
import numpy as np
import h5py
#from six.moves import xrange  # pylint: disable=redefined-builtin

#from tensorflow.contrib.learn.python.learn.datasets import base
from tensorflow.python.framework import dtypes

Datasets = collections.namedtuple('Datasets', ['train', 'validation', 'test'])

def _read32(bytestream):
  dt = np.dtype(np.uint32).newbyteorder('>')
  return np.frombuffer(bytestream.read(4), dtype=dt)[0]

    
def group_cat(i):
    if int(i) == 1:
        return np.array([1.0,0.0])
    else:
        return np.array([0.0,1.0])

class DataSet(object):

  def __init__(self,
               images,
               labels,
               fake_data=False,
               one_hot=False,
               dtype=dtypes.float32,
               reshape=True,
               channels = 1):
    """Construct a DataSet.
    one_hot arg is used only if fake_data is true.  `dtype` can be either
    `uint8` to leave the input as `[0, 255]`, or `float32` to rescale into
    `[0, 1]`.
    """
    dtype = dtypes.as_dtype(dtype).base_dtype
    if dtype not in (dtypes.uint8, dtypes.float32):
      raise TypeError('Invalid image dtype %r, expected uint8 or float32' %
                      dtype)
    if fake_data:
      self._num_examples = 10000
      self.one_hot = one_hot
    else:
      assert images.shape[0] == labels.shape[0], (
          'images.shape: %s labels.shape: %s' % (images.shape, labels.shape))
      self._num_examples = images.shape[0]

      # Convert shape from [num examples, rows, columns, depth]
      # to [num examples, rows*columns] (assuming depth == 1)
      if reshape:
        assert images.shape[3] == 1
        images = images.reshape(images.shape[0],
                                images.shape[1] * images.shape[2])
      if dtype == dtypes.float32:
        # Convert from max of .25 to 1.
        # Convert from [0, 255] -> [0.0, 1.0].
        images = images.astype(np.float32)
        images = np.multiply(images, 4)
    self._images = images
    self._labels = labels
    self._epochs_completed = 0
    self._index_in_epoch = 0

  @property
  def images(self):
    return self._images

  @property
  def labels(self):
    return self._labels

  @property
  def num_examples(self):
    return self._num_examples

  @property
  def epochs_completed(self):
    return self._epochs_completed

  def next_batch(self, batch_size, fake_data=False):
    """Return the next `batch_size` examples from this data set."""
    if fake_data:
      fake_image = [1] * 784
      if self.one_hot:
        fake_label = [1] + [0] * 9
      else:
        fake_label = 0
      return [fake_image for _ in xrange(batch_size)], [
          fake_label for _ in xrange(batch_size)
      ]
    start = self._index_in_epoch
    self._index_in_epoch += batch_size
    if self._index_in_epoch > self._num_examples:
      # Finished epoch
      self._epochs_completed += 1
      # Shuffle the data
      perm = np.arange(self._num_examples)
      np.random.shuffle(perm)
      self._images = self._images[perm]
      self._labels = self._labels[perm]
      # Start next epoch
      start = 0
      self._index_in_epoch = batch_size
      assert batch_size <= self._num_examples
    end = self._index_in_epoch
    return self._images[start:end], self._labels[start:end]


def read_data_sets(datafile,
                   fake_data=False,
                   one_hot=False,
                   dtype=dtypes.float32,
                   reshape=False,
                   validation_size=0,
                   fraction=1,
                   channels=1,
                   imagery='alff'):


    f = h5py.File(datafile,'r')
    sub = f["subjects"]
    ids = [x for x in sub]

    filt_ids = []
    for ID in ids:
         #if sub[ID].attrs.get('AGE_AT_SCAN') > 16.0 and sub[ID].attrs.get('SEX') == 1:
            filt_ids.append(ID)

    import random
    #random.seed(5)
    random.shuffle(filt_ids)

    train_ids = filt_ids[0:int(len(filt_ids)*.75)]
    test_ids = filt_ids[int(len(filt_ids)*.75):]

    chans = [x for x in sub[ids[0]]]
    chans = chans[:channels]

    def channel_imgs(chan, id_list):
        channel_img = np.ravel(sub[id_list[0]][chan][2:58,6:70,4:52])
        for i,ID in enumerate(id_list[1:len(id_list)//fraction]):
            if i%10 == 0:
                print('.', end="")
            channel_img = np.vstack( (channel_img, np.ravel(sub[ID][chan][2:58,6:70,4:52]) ) )

        print('')
        return channel_img




    # trainimgs = np.ravel(sub[train_ids[0]][chans[0]][2:58,6:70,4:52])
    # for i,ID in enumerate(train_ids[1:len(train_ids)//fraction]):
    #     if i%10 == 0:
    #         print('.', end="")
    #     trainimgs = np.vstack( (trainimgs, np.ravel(sub[ID][chans[0]][2:58,6:70,4:52]) ) )
    #
    #
    # testimgs = np.ravel(sub[test_ids[0]][chans[0]][2:58,6:70,4:52])
    # for i,ID in enumerate(test_ids[1:len(test_ids)//fraction]):
    #     if i%10 == 0:
    #         print('.', end="")
    #     testimgs = np.vstack( (testimgs, np.ravel(sub[ID][chans[0]][2:58,6:70,4:52])) )

    trainimgs = channel_imgs(chans[0], train_ids)
    testimgs = channel_imgs(chans[0], test_ids)

    if channels > 1:
        for ch in chans[1:]:
           trainimgs = np.dstack(   ( trainimgs, channel_imgs(ch, train_ids) ) )
           testimgs = np.dstack(    ( testimgs,  channel_imgs(ch, test_ids)  ) )


    trainlabels = group_cat(sub[train_ids[0]].attrs.get('DX_GROUP'))
    for i,ID in enumerate(train_ids[1:len(train_ids)//fraction]):
        trainlabels = np.vstack( (trainlabels, group_cat(sub[ID].attrs.get('DX_GROUP'))) )

    testlabels = group_cat(sub[test_ids[0]].attrs.get('DX_GROUP'))
    for i,ID in enumerate(test_ids[1:len(test_ids)//fraction]):
        testlabels = np.vstack( (testlabels, group_cat(sub[ID].attrs.get('DX_GROUP'))) )

    # trainimgs = channel_imgs('alff', train_ids)
    # testimgs = channel_imgs('alff', test_ids)

    #validation_images = train_images[:validation_size]
    #validation_labels = train_labels[:validation_size]
    #train_images = size:]
    #train_labels = train_labels[validation_size:]
    validation = None

    train = DataSet(trainimgs, trainlabels, dtype=dtype, reshape=reshape)
    #validation = DataSet(validation_images,
    #                   validation_labels,
    #                   dtype=dtype,
    #                   reshape=reshape)
    test = DataSet(testimgs, testlabels, dtype=dtype, reshape=reshape)

    return Datasets(train=train, validation=validation, test=test)


def load_data(datafile='./data/AllSubjects4cat.hdf5'):
  return read_data_sets(datafile)
