
# coding: utf-8

# In[1]:
from __future__ import print_function

import os

import matplotlib.pyplot as plt

os.environ["PATH"] += os.pathsep + 'E:/Graphviz2.38/bin'

version = 'v2.0'
project = 'test'
ios = 0 # 0->issue，1->solution
i_train = -1;# 0->GPU training，1->CPU prediction，-1->CPU training and prediction(only for issue)

import tensorflow as tf
# import keras.backend.tensorflow_backend as KTF
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
if i_train == 0:
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
config = tf.compat.v1.ConfigProto()
config.gpu_options.allow_growth=True
config.gpu_options.per_process_gpu_memory_fraction = 0.7


# In[2]:
import os
import math
import sys
import numpy as np
from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences
from keras.utils import to_categorical
from keras.layers import Dense, Input, GlobalMaxPooling1D, Dropout, concatenate, Concatenate, GlobalAveragePooling1D, Multiply
from keras.layers import Conv1D, MaxPooling1D, Embedding, Bidirectional, LSTM, Lambda
from keras.models import Model
from models.custom_metrics import hamming_score, f1
from keras import optimizers, regularizers
from keras.callbacks import EarlyStopping
# import matplotlib.pyplot as plt
import logging, pickle
from models.attention import *
from keras.utils import plot_model
from models.metrics import *
from keras_bert import extract_embeddings, POOL_NSP, POOL_MAX
from keras_bert import load_trained_model_from_checkpoint
from models.Transformer_Attention import *
from rcnn import *
from keras.backend import stack
# config_path = 'C:\\Users\\52993\\.keras\\datasets\\wwm_uncased_L-24_H-1024_A-16\\bert_config.json'
# checkpoint_path = 'C:\\Users\\52993\\.keras\\datasets\\wwm_uncased_L-24_H-1024_A-16\\bert_model.ckpt'



# In[3]:
# conv_units = int(sys.argv[1])
# filter_size = 3
# pooling_size = 3
# dropout_rate = float(sys.argv[2])
# dense_units = int(sys.argv[3])
# max_len = int(sys.argv[4])

rnn_units = 128
conv_units = 1024 #int(sys.argv[1])
filter_size = 3
pooling_size = 3
dropout_rate = 0.6 #float(sys.argv[2])
dense_units = 256 #int(sys.argv[3])
max_len = 800 #int(sys.argv[4])
WINDOW_SIZE = 11
context_conv_units = 128 #int(sys.argv[5])
context_filter_size = filter_size
context_pooling_size = pooling_size
context_dropout_rate = dropout_rate
context_dense_units = 128 #int(sys.argv[6])
MAX_TEST_DATA = 5000

if ios == 1:
    MAX_TEST_DATA = 250

#logging.basicConfig(filename='../res/cnn_feature/{}_{}_{}_{}.log'.format(conv_units, dropout_rate, dense_units, max_len), level=logging.INFO)

BASE_DIR = ''
GLOVE_DIR = '../data/'
EMBEDDING_FILE = 'glove.6B.100d.txt'
MAX_SEQUENCE_LENGTH = max_len
MAX_NUM_WORDS = 20000
EMBEDDING_DIM = 100
EMBED_INIT_GLOVE = True
FEAT_NUM = 24
ATTR_NUM = 128
MAX_SENTENCE = 8

# In[4]:


train_file = '../data/cross_validation_dataset/t_v_test_' + project + '/train.tsv'
valid_file = '../data/cross_validation_dataset/t_v_test_' + project + '/valid.tsv'
test_file = '../data/cross_validation_dataset/t_v_test_' + project + '/' + project + '.tsv'


train_feat_file = '../data/cross_validation_dataset/t_v_test_' + project + '/train_features.tsv'
valid_feat_file = '../data/cross_validation_dataset/t_v_test_' + project + '/valid_features.tsv'
test_feat_file = '../data/cross_validation_dataset/t_v_test_' + project + '/' + project + '_features.tsv'

if ios == 1:
    train_file = '../data/cross_validation_dataset/t_v_test_' + project + '/train.tsv'
    valid_file = '../data/cross_validation_dataset/t_v_test_' + project + '/valid.tsv'
    test_file = '../data/cross_validation_dataset/t_v_test_' + project + '/' + project + '_issue.tsv'


    train_feat_file = '../data/cross_validation_dataset/t_v_test_' + project + '/train_features.tsv'
    valid_feat_file = '../data/cross_validation_dataset/t_v_test_' + project + '/valid_features.tsv'
    test_feat_file = '../data/cross_validation_dataset/t_v_test_' + project + '/' + project + '_features_issue.tsv'


# In[5]:


# first, build index mapping words in the embeddings set to their embedding vector

print('Indexing word vectors.')

embeddings_index = {}#存放字典的键值对
with open(os.path.join(GLOVE_DIR, EMBEDDING_FILE), encoding='utf8') as f:
    for line in f:
        values = line.split(' ')
        word = values[0]
        coefs = np.asarray(values[1:], dtype='float32')
        embeddings_index[word] = coefs

print('Found %s word vectors.' % len(embeddings_index))


# In[6]:

# second, prepare text samples and their labels
print('Processing text dataset')

texts = []  # list of text samples
# labels_index = {'OQ': 0, 'OP': 1, 'OF': 2, 'FD': 3, 'FQ': 4, 'CQ': 5, 'AE': 6, 'AC': 7, 'IG': 8, 'CC': 9, 'UF': 10,
#                 'PF': 11, 'NF': 12, 'GG': 13, 'JK': 14}
labels_index = {'0': 0, '1': 1}
id2label = {v: k for k, v in labels_index.items()}
classes_num = len(labels_index)

labels_index_multi = {'0': 0, '1': 1, '2': 2}
id2label_multi = {v: k for k, v in labels_index_multi.items()}
classes_num_multi = len(labels_index_multi)
num_train_sentences, num_valid_sentences, num_test_sentences = [], [], []
def load_data_and_labels(data_file, label_info):
    x = []
    y = []
    y_issue_ret = []
    y_multi_ret = []
    i = 0
    x_dialog, y_dialog, y_issue, y_multi = [], [], [], []
    x_whole_dialog, x_each_dialog = [], []
    issue_mark = 0
    with open(data_file, encoding='utf8') as raw_data:
        for line in raw_data:
            i += 1
#             print(i)
            if line != '\n':
                x_each_dialog.append(line)
                line = line.strip()
                tokens = line.split('\t')
                # prediction
                if label_info == 'test' and ios == 0 :
                    tokens.append('0')
                    tokens.append('0')
                    tokens.append('0')
                    tokens.append('0')
                elif label_info == 'test' and ios == 1 :
                    tokens.append('1')
                    tokens.append('1')
                    tokens.append('1')
                    tokens.append('1')

                # print(tokens)
                labels = tokens[3].split('_')
                issue_labels = tokens[5]
                new_classes_labels = tokens[6]
                issue_mark = int(tokens[4])
                x_dialog.append(tokens[1])
                each_y = [0] * classes_num
                each_y_issue = [0] * classes_num
                each_y_multi = [0] * classes_num_multi
                for label in labels:
                    each_y[labels_index[label]] = 1
                for label_issue in issue_labels:
                    each_y_issue[labels_index[label_issue]] = 1
                for label_multi in new_classes_labels:
                    each_y_multi[labels_index_multi[label_multi]] = 1
                y_dialog.append(each_y)
                y_issue.append(each_y_issue)
                y_multi.append(each_y_multi)
            else:
                x_whole_dialog.append(x_each_dialog)
                x_each_dialog = []
                # Padding of dialogues.
                if len(x_dialog) > MAX_SENTENCE:
                    if label_info == 'train':
                        num_train_sentences.append(MAX_SENTENCE)
                    if label_info == 'valid':
                        num_valid_sentences.append(MAX_SENTENCE)
                    if label_info == 'test':
                        num_test_sentences.append(MAX_SENTENCE)
                    x_dialog = x_dialog[0:MAX_SENTENCE]
                    y_dialog = y_dialog[0:MAX_SENTENCE]
                    y_issue = y_issue[0:MAX_SENTENCE]
                    y_multi = y_multi[0:MAX_SENTENCE]
                elif len(x_dialog) <= MAX_SENTENCE:
                    if label_info == 'train':
                        num_train_sentences.append(len(x_dialog))
                    if label_info == 'valid':
                        num_valid_sentences.append(len(x_dialog))
                    if label_info == 'test':
                        num_test_sentences.append(len(x_dialog))
                    x_dialog += [''] * (MAX_SENTENCE - len(x_dialog))

                    y_dialog += [[1, 0]] * (MAX_SENTENCE - len(y_dialog))
                    y_issue += [[1, 0]] * (MAX_SENTENCE - len(y_issue))
                    y_multi += [[1, 0, 0]] * (MAX_SENTENCE - len(y_multi))
                x.append(x_dialog)
                y.append(y_dialog)
                y_issue_ret.append(y_issue)
                y_multi_ret.append(y_multi)
                # if issue_mark == 0:
                #     y_issue.append([1, 0])
                # else:
                #     y_issue.append([0, 1])
                x_dialog, y_dialog, y_issue, y_multi = [], [], [], []
    return x, y, y_issue_ret, y_multi_ret, x_whole_dialog


x_train, y_train, y_train_issue, y_train_multi, train_whole = load_data_and_labels(train_file, 'train')
x_valid, y_valid, y_valid_issue, y_valid_multi, valid_whole = load_data_and_labels(valid_file, 'valid')
# x_test, y_test, y_test_issue = load_data_and_labels(test_file)
x_test, y_test, y_test_issue, y_test_multi, test_whole = load_data_and_labels(test_file, 'test')
x_temp_test, y_temp_test, y_temp_test_issue, y_temp_test_multi, test_temp_whole = \
    x_test, y_test, y_test_issue, y_test_multi, test_whole


# MAX_SEQUENCE_LENGTH = max(max(map(len, x_train)), max(map(len, x_valid)), max(map(len, x_test)))
# print(MAX_SEQUENCE_LENGTH)


print('Found %s texts.' % len(x_train + x_valid + x_test))

# In[7]:

def load_features(data_file):
    x = []
    i = 0
    x_dialog = []
    len_features = 0
    with open(data_file, encoding='utf8') as raw_data:
        for line in raw_data:
            i += 1
            #             print(i)
            if line != '\n':
                line = line.strip()
                tokens = line.split('\t')
                features = list(map(float, tokens[1].split()))
                len_features = len(features)
                x_dialog.append(features)
            else:
                if len(x_dialog) > MAX_SENTENCE:
                    x_dialog = x_dialog[0:MAX_SENTENCE]
                elif len(x_dialog) < MAX_SENTENCE:
                    x_dialog += [[0] * len_features] * (MAX_SENTENCE - len(x_dialog))
                x.append(x_dialog)
                x_dialog = []
    return np.array(x)


x_train_feat = load_features(train_feat_file)
x_val_feat = load_features(valid_feat_file)
x_test_feat = load_features(test_feat_file)
x_temp_test_feat = x_test_feat

print('Found %s features.' % len(x_train_feat[0]))

# In[8]:
len_test_data = len(x_test)
max_test_number = int(len_test_data/MAX_TEST_DATA) + 1

test_out = test_file.replace('.tsv', '') + '_issue.tsv'
test_feat_out = test_feat_file.replace('.tsv', '') + '_issue.tsv'
if ios == 1:
    test_out = test_file.replace('_issue.tsv', '') + '_ispair.txt'

y_train_store, y_valid_store = y_train, y_valid
x_train_store, x_valid_store = x_train, x_valid
num_test_temp_sentences = num_test_sentences
with open(test_out, 'w', encoding='utf8') as tout, open(test_feat_out, 'w', encoding='utf8') as tfout:
    for index_out in range(max_test_number):

        if index_out < max_test_number - 1:
            x_test, y_test, y_test_issue, y_test_multi, test_whole, num_test_sentences = x_temp_test[index_out * MAX_TEST_DATA: (index_out + 1) * MAX_TEST_DATA], \
                                                         y_temp_test[index_out * MAX_TEST_DATA: (index_out + 1) * MAX_TEST_DATA], \
                                                         y_temp_test_issue[index_out * MAX_TEST_DATA: (index_out + 1) * MAX_TEST_DATA], \
                                                         y_temp_test_multi[index_out * MAX_TEST_DATA: (index_out + 1) * MAX_TEST_DATA], \
                                                         test_temp_whole[index_out * MAX_TEST_DATA: (index_out + 1) * MAX_TEST_DATA], \
                                                         num_test_temp_sentences[index_out * MAX_TEST_DATA: (index_out + 1) * MAX_TEST_DATA]
            x_test_feat = x_temp_test_feat[index_out * MAX_TEST_DATA: (index_out + 1) * MAX_TEST_DATA]
        else:
            x_test, y_test, y_test_issue, y_test_multi, test_whole, num_test_sentences = x_temp_test[index_out * MAX_TEST_DATA:], \
                                                         y_temp_test[index_out * MAX_TEST_DATA:], \
                                                         y_temp_test_issue[index_out * MAX_TEST_DATA:], \
                                                         y_temp_test_multi[index_out * MAX_TEST_DATA:], \
                                                         test_temp_whole[index_out * MAX_TEST_DATA:], \
                                                         num_test_temp_sentences[index_out * MAX_TEST_DATA:]
            x_test_feat = x_temp_test_feat[index_out * MAX_TEST_DATA:]

        labels = np.array(y_train_store + y_valid_store + y_test)
        # finally, vectorize the text samples into a 2D integer tensor
        tokenizer = Tokenizer(num_words=MAX_NUM_WORDS)
        x_train_sample, x_valid_sample, x_test_sample = [], [], []
        for each_train in x_train_store:
            x_train_sample += each_train
        for each_valid in x_valid_store:
            x_valid_sample += each_valid
        for each_test in x_test:
            x_test_sample += each_test
        fit_sample = []
        for data in x_train_sample + x_valid_sample:
            if data != '':
                fit_sample.append(data)
        tokenizer.fit_on_texts(fit_sample)
        sequences = tokenizer.texts_to_sequences(x_train_sample + x_valid_sample + x_test_sample)
        message_sequence = x_train_sample + x_valid_sample + x_test_sample
        # sequence_new = []
        # num_dialogs = int(len(message_sequence)/MAX_SENTENCE)
        # for i in range(num_dialogs):
        #     dialog_each = message_sequence[MAX_SENTENCE * i: MAX_SENTENCE * (i + 1)]
        #     sequence_new += extract_embeddings(model_path, dialog_each, output_layer_num=1, poolings=[POOL_NSP, POOL_MAX])
        # sequences_new = extract_embeddings(model_path, x_train_sample + x_valid_sample + x_test_sample, output_layer_num=4, poolings=[POOL_NSP, POOL_MAX])
        word_index = tokenizer.word_index
        print('Found %s unique tokens.' % len(word_index))

        data = pad_sequences(sequences, maxlen=MAX_SEQUENCE_LENGTH)

        # labels = to_categorical(np.asarray(y_train))
        print('Shape of data tensor:', data.shape)
        print('Shape of label tensor:', labels.shape)
        print('Shape of feature tensor:', x_train_feat.shape)

       # In[9]:


        print('Preparing embedding matrix.')

        # prepare embedding matrix
        num_words = min(MAX_NUM_WORDS, len(word_index) + 1)

        if EMBED_INIT_GLOVE:

            embedding_matrix = np.zeros((num_words, EMBEDDING_DIM))
            for word, i in word_index.items():
                if i >= MAX_NUM_WORDS:
                    continue
                embedding_vector = embeddings_index.get(word)
                if embedding_vector is not None:
                    # words not found in embedding index will be all-zeros.
                    embedding_matrix[i] = embedding_vector


            # note that we set trainable = False so as to keep the embeddings fixed
            embedding_layer_s = Embedding(num_words,
                                        EMBEDDING_DIM,
                                        weights=[embedding_matrix],
                                        input_length=MAX_SEQUENCE_LENGTH,
                                        trainable=False)

            embedding_layer_c = Embedding(num_words,
                                        EMBEDDING_DIM,
                                        weights=[embedding_matrix],
                                        input_length=MAX_SEQUENCE_LENGTH * WINDOW_SIZE,
                                        trainable=False)

        else:
            embedding_layer = Embedding(num_words,
                                        EMBEDDING_DIM,
                                        embeddings_initializer='uniform',
                                        input_length=MAX_SEQUENCE_LENGTH * MAX_SENTENCE)


         # In[10]:

        data_group, data_unit = [], []
        for i, data_each in enumerate(data):
            if i % MAX_SENTENCE == 0 and i > 0:
                data_group.append(data_unit)
                data_unit = [list(data_each)]
            else:
                data_unit.append(list(data_each))
        data_group.append(data_unit)

        num_validation_samples = len(y_valid)
        num_test_samples = len(y_test)
        num_train_samples = len(y_train)
        num_total_samples = len(labels)


        x_train = data_group[:num_train_samples]
        y_train = labels[:num_train_samples]
        x_val = data_group[num_train_samples: num_train_samples + num_validation_samples]
        y_val = labels[num_train_samples: num_train_samples + num_validation_samples]
        x_test = data_group[-num_test_samples:]
        y_test = labels[-num_test_samples:]

        assert len(x_train) + len(x_val) + len(x_test) == len(labels)
        assert len(y_train) + len(y_val) + len(y_test) == len(labels)


        # load sequence features
        # def load_sequence_features(data_file):
        #     x = []
        #     i = 0
        #     with open(data_file, encoding='utf8') as raw_data:
        #         for line in raw_data:
        #             i += 1
        # #             print(i)
        #             if line != '\n':
        #                 line = line.strip()
        #                 tokens = line.split('\t')
        #                 features = tokens[1].split()
        #                 abs_pos = int(features[10])
        #                 x.append(abs_pos)
        #     return np.array(x)

        # x_train_sequence_feat = load_sequence_features(train_feat_file)
        # x_val_sequence_feat = load_sequence_features(valid_feat_file)
        # x_test_sequence_feat = load_sequence_features(test_feat_file)


        def gen_data_with_context(x):
            # incorporate pervious one and future one utterances as context 497x40x800

            # x_trans = np.zeros((num_sample, size_sample * 3),  dtype=int)
            x_trans, x_sentence = [], []
            mini_windows = int((WINDOW_SIZE - 1)/2)
            for dialog_embedding in x:
                for i, sentence_embedding in enumerate(dialog_embedding):
                    start_index = i - mini_windows
                    x_pre, x_post = [], []
                    for add_index in range(mini_windows):
                        index_this_sentence = start_index + add_index
                        if index_this_sentence < 0:
                            x_pre += [0] * len(sentence_embedding)
                        else:
                            x_pre += dialog_embedding[index_this_sentence]
                    for add_index in range(mini_windows):
                        if i + add_index >= MAX_SENTENCE:
                            x_post += [0] * len(sentence_embedding)
                        else:
                            x_post += dialog_embedding[i + add_index]
                        # x_sentence.append([0] * len(sentence_embedding) + sentence_embedding + dialog_embedding[i + 1])
                    x_sentence.append(x_pre + sentence_embedding + x_post)#x_pre + sentence_embedding + x_post 为 一维列表，长度为（5+1+5）*800，其中5+1+5即为WINDOW_SIZE
                    # elif i < MAX_SENTENCE - mini_windows:
                    #     x_sentence.append(dialog_embedding[i - 1] + sentence_embedding + dialog_embedding[i + 1])
                    # else:
                    #
                    #     x_sentence.append(dialog_embedding[i - 1] + sentence_embedding + [0] * len(sentence_embedding))
                x_trans.append(x_sentence)
                x_sentence = []
            x_trans = np.array(x_trans)
            return x_trans


        x_train_with_context = gen_data_with_context(x_train).astype(np.float32)
        x_val_with_context = gen_data_with_context(x_val).astype(np.float32)
        x_test_with_context = gen_data_with_context(x_test).astype(np.float32)
        x_train_feat_with_context = gen_data_with_context(x_train_feat.tolist()).astype(np.float32)
        x_val_feat_with_context = gen_data_with_context(x_val_feat.tolist()).astype(np.float32)
        x_test_feat_with_context = gen_data_with_context(x_test_feat.tolist()).astype(np.float32)
        x_train = np.array(x_train)
        x_val = np.array(x_val)
        x_test = np.array(x_test)
        y_train = np.array(y_train)
        y_val = np.array(y_val)
        y_test = np.array(y_test)
        y_train_issue = np.array(y_train_issue)
        y_valid_issue = np.array(y_valid_issue)
        y_test_issue = np.array(y_test_issue)
        y_train_multi = np.array(y_train_multi)
        y_valid_multi = np.array(y_valid_multi)
        y_test_multi = np.array(y_test_multi)


        # In[11]:

        def retrieve_candidate_info(input_x, num_sentences, issue_list):
            list_input_x = input_x.tolist()
            result_retrieve = []
            for i, data_input in enumerate(list_input_x):
                if issue_list[i][0][1] == 1:
                    result_retrieve += data_input[: num_sentences[i]]
                    # result_retrieve += data_input[0:1]
            return np.array(result_retrieve)


        x_train_reshape = retrieve_candidate_info(x_train, num_train_sentences, y_train_issue)
        x_val_reshape = retrieve_candidate_info(x_val, num_valid_sentences, y_valid_issue)
        x_test_reshape = retrieve_candidate_info(x_test, num_test_sentences, y_test_issue)

        x_train_feat_reshape = retrieve_candidate_info(x_train_feat, num_train_sentences, y_train_issue)
        x_val_feat_reshape = retrieve_candidate_info(x_val_feat, num_valid_sentences, y_valid_issue)
        x_test_feat_reshape = retrieve_candidate_info(x_test_feat, num_test_sentences, y_test_issue)

        x_train_with_context_reshape = retrieve_candidate_info(x_train_with_context, num_train_sentences, y_train_issue)
        x_val_with_context_reshape = retrieve_candidate_info(x_val_with_context, num_valid_sentences, y_valid_issue)
        x_test_with_context_reshape = retrieve_candidate_info(x_test_with_context, num_test_sentences, y_test_issue)

        x_train_feat_with_context_reshape = retrieve_candidate_info(x_train_feat_with_context, num_train_sentences, y_train_issue)
        x_val_feat_with_context_reshape = retrieve_candidate_info(x_val_feat_with_context, num_valid_sentences, y_valid_issue)
        x_test_feat_with_context_reshape = retrieve_candidate_info(x_test_feat_with_context, num_test_sentences, y_test_issue)

        y_train_reshape = retrieve_candidate_info(y_train, num_train_sentences, y_train_issue)
        y_val_reshape = retrieve_candidate_info(y_val, num_valid_sentences, y_valid_issue)
        y_test_reshape = retrieve_candidate_info(y_test, num_test_sentences, y_test_issue)

        y_train_issue_reshape = retrieve_candidate_info(y_train_issue, num_train_sentences, y_train_issue)
        y_valid_issue_reshape = retrieve_candidate_info(y_valid_issue, num_valid_sentences, y_valid_issue)
        y_test_issue_reshape = retrieve_candidate_info(y_test_issue, num_test_sentences, y_test_issue)

        y_train_multi_reshape = retrieve_candidate_info(y_train_multi, num_train_sentences, y_train_issue)
        y_valid_multi_reshape = retrieve_candidate_info(y_valid_multi, num_valid_sentences, y_valid_issue)
        y_test_multi_reshape = retrieve_candidate_info(y_test_multi, num_test_sentences, y_test_issue)
        # x_train_reshape = np.reshape(x_train, (-1, max_len))
        # x_val_reshape = np.reshape(x_val, (-1, max_len))
        # x_test_reshape = np.reshape(x_test, (-1, max_len))
        # x_train_feat_reshape = np.reshape(x_train_feat, (-1, FEAT_NUM))
        # x_val_feat_reshape = np.reshape(x_val_feat, (-1, FEAT_NUM))
        # x_test_feat_reshape = np.reshape(x_test_feat, (-1, FEAT_NUM))
        # x_train_with_context_reshape = np.reshape(x_train_with_context, (-1, MAX_SEQUENCE_LENGTH * 3))
        # x_val_with_context_reshape = np.reshape(x_val_with_context, (-1, MAX_SEQUENCE_LENGTH * 3))
        # x_test_with_context_reshape = np.reshape(x_test_with_context, (-1, MAX_SEQUENCE_LENGTH * 3))
        # y_train_reshape = np.reshape(y_train, (-1, 2))
        # y_val_reshape = np.reshape(y_val, (-1, 2))
        # y_test_reshape = np.reshape(y_test, (-1, 2))
        # y_train_issue_reshape = np.reshape(y_train_issue, (-1, 2))
        # y_valid_issue_reshape = np.reshape(y_valid_issue, (-1, 2))
        # y_test_issue_reshape = np.reshape(y_test_issue, (-1, 2))
        # y_train_multi_reshape = np.reshape(y_train_multi, (-1, 3))
        # y_valid_multi_reshape = np.reshape(y_valid_multi, (-1, 3))
        # y_test_multi_reshape = np.reshape(y_test_multi, (-1, 3))


        #In[12]

        x_train_single = x_train[:, 0, :]
        x_train_feat_single = x_train_feat[:, 0, :]
        x_train_feat_with_context_single = x_train_feat_with_context[:, 0, :]
        x_train_with_context_single = x_train_with_context[:, 0, :]
        y_train_issue_single = y_train_issue[:, 0, :]
        x_val_single = x_val[:, 0, :]
        x_val_feat_single = x_val_feat[:, 0, :]
        x_val_feat_with_context_single = x_val_feat_with_context[:, 0, :]
        x_val_with_context_single = x_val_with_context[:, 0, :]
        y_val_issue_single = y_valid_issue[:, 0, :]
        x_test_single = x_test[:, 0, :]
        x_test_feat_single = x_test_feat[:, 0, :]
        x_test_feat_with_context_single = x_test_feat_with_context[:, 0, :]
        x_test_with_context_single = x_test_with_context[:, 0, :]
        y_test_issue_single = y_test_issue[:, 0, :]


        #In[13]


        sequence_input = Input(shape=(MAX_SEQUENCE_LENGTH,), dtype='int32')
        feature_input = Input(shape=(FEAT_NUM * WINDOW_SIZE,), dtype='float32')
        context_input = Input(shape=(MAX_SEQUENCE_LENGTH * WINDOW_SIZE,), dtype='float32')


        embeddings_t = Embedding(MAX_NUM_WORDS, ATTR_NUM)(sequence_input)
        embeddings_t = Position_Embedding()(embeddings_t)

        attr_result_1 = Self_Attention(ATTR_NUM)(embeddings_t)
        attr_result_1 = GlobalAveragePooling1D()(attr_result_1)
        attr_result_1 = Dropout(dropout_rate)(attr_result_1)


        embeddings = Embedding(MAX_NUM_WORDS, ATTR_NUM)(context_input)

        attr_result = Self_Attention(ATTR_NUM)(embeddings)
        attr_result = GlobalMaxPooling1D()(attr_result)
        attr_result = Dropout(dropout_rate)(attr_result)



        x_current = sequence_input
        x_left = Lambda(lambda x: tf.concat([tf.expand_dims(x[:,0],axis=1),x[:,0:-1]], axis=1))(sequence_input)
        x_right = Lambda(lambda x: tf.concat([x[:,1:],tf.expand_dims(x[:,-1],axis=1)], axis=1))(sequence_input)
        # print('x_left before Embedding', x_left)
        # print('x_right before Embedding', x_right)

        embedding_current = embedding_layer_s(x_current)
        embedding_left = embedding_layer_s(x_left)
        embedding_right = embedding_layer_s(x_right)

        x_left = SimpleRNN(rnn_units, return_sequences=True)(embedding_left)
        x_right = SimpleRNN(rnn_units, return_sequences=True, go_backwards=True)(embedding_right)
        x_right = Lambda(lambda x: K.reverse(x, axes=1))(x_right)
        # print('x_left', x_left)
        # print('embedding_current', embedding_current)
        # print('x_right', x_right)
        concat = Concatenate(axis=2)([x_left, embedding_current, x_right])
        x = Conv1D(conv_units, filter_size, activation='tanh')(concat)
        x = GlobalMaxPooling1D()(x)
        x = Dense(dense_units, activation='relu')(x)


        length_pre_post = int((WINDOW_SIZE - 1) / 2)  # 5

        context_embedding_input = embedding_layer_c(context_input)
        x_pre_current = Lambda(lambda x: x[:, 0: MAX_SEQUENCE_LENGTH * length_pre_post, :])(context_embedding_input)
        x_post_current = Lambda(lambda x: x[:, MAX_SEQUENCE_LENGTH * (length_pre_post + 1): -1, :])(context_embedding_input)

        #x_pre RNN
        x_pre_left = Lambda(lambda x: tf.concat([tf.expand_dims(x[:, 0, :], axis=1), x[:, 0: -1, :]], axis=1))(x_pre_current)
        x_pre_right = Lambda(lambda x: tf.concat([x[:, 1:, :], tf.expand_dims(x[:, -1, :], axis=1)], axis=1))(x_pre_current)

        x_pre_left = SimpleRNN(rnn_units, return_sequences=True)(x_pre_left)
        x_pre_right = SimpleRNN(rnn_units, return_sequences=True, go_backwards=True)(x_pre_right)
        x_pre_right = Lambda(lambda x: K.reverse(x,axes=1))(x_pre_right)
        concat = Concatenate(axis=2)([x_pre_left, x_pre_current, x_pre_right])
        x_pre = Conv1D(conv_units, filter_size, activation='tanh')(concat)
        x_pre = GlobalMaxPooling1D()(x_pre)
        x_pre = Dense(dense_units, activation='relu')(x_pre)

        #x_post RNN
        x_post_left = Lambda(lambda x: tf.concat([tf.expand_dims(x[:, 0, :], axis=1), x[:, 0: -1, :]], axis=1))(x_post_current)
        x_post_right = Lambda(lambda x: tf.concat([x[:, 1:, :], tf.expand_dims(x[:, -1, :], axis=1)], axis=1))(x_post_current)

        x_post_left = SimpleRNN(rnn_units, return_sequences=True)(x_post_left)
        x_post_right = SimpleRNN(rnn_units, return_sequences=True, go_backwards=True)(x_post_right)
        x_post_right = Lambda(lambda x: K.reverse(x, axes=1))(x_post_right)
        concat = Concatenate(axis=2)([x_post_left, x_post_current, x_post_right])
        x_post = Conv1D(conv_units, filter_size, activation='tanh')(concat)
        x_post = GlobalMaxPooling1D()(x_post)
        x_post = Dense(dense_units, activation='relu')(x_post)





        concat = Concatenate()([attr_result_1, feature_input, attr_result])
        # attention
        att_prob_issue = Dense(concat.shape[1], activation='sigmoid', name='att_vec')(concat)
        att_mul_issue = Multiply()([concat, att_prob_issue])

        preds_issue_new = Dense(len(labels_index), activation='sigmoid', name='issue_dense')(att_mul_issue)
        model2 = Model([sequence_input, feature_input, context_input], preds_issue_new)

        model2.compile(loss='binary_crossentropy',
                      optimizer='adam',
                      metrics=['binary_accuracy'])

        es = EarlyStopping(monitor='val_loss',
                          min_delta=0,
                          patience=2,
                          verbose=0, mode='auto')

        if ios == 0:

            weights_path = '../weights/' + version + '/' + project
            if not os.path.exists(weights_path):
                os.makedirs(weights_path)
            weights = weights_path + '/weights_issue_classification_only.h5'

            if i_train == 0 or i_train == -1:
                model2.summary()
                history2 = model2.fit([x_train_single, x_train_feat_with_context_single, x_train_with_context_single], y_train_issue_single,
                          batch_size=8,
                          epochs=2,
                          callbacks=[es],
                          validation_data=([x_val_single, x_val_feat_with_context_single, x_val_with_context_single], y_val_issue_single))

                model2.save_weights(weights, overwrite=True)


                plt.plot(history2.history['loss'])
                plt.plot(history2.history['val_loss'])
                plt.plot(history2.history['val_binary_accuracy'])
                plt.title('model loss')
                plt.ylabel('loss/acc')
                plt.xlabel('epoch')
                plt.legend(['train', 'val', 'val_acc'], loc='upper left')
                # plt.show()

                figname = project + '.png'
                figure_save_path = "../fig/" + version
                if not os.path.exists(figure_save_path):
                    os.makedirs(figure_save_path)
                plt.savefig(os.path.join(figure_save_path, figname))


                plt.close()

            if i_train == 1 or i_train == -1:
                model2.load_weights(weights, by_name=True)
                pred_test = model2.predict([x_test_single, x_test_feat_with_context_single, x_test_with_context_single])

                # Prediction and Storage
                for j, pred_each in enumerate(pred_test):
                    if pred_each[1] > pred_each[0]:
                        dialog_selected = test_whole[j]
                        length_output = len(dialog_selected)
                        if length_output > MAX_SENTENCE:
                            dialog_selected = dialog_selected[: MAX_SENTENCE]
                            length_output = MAX_SENTENCE
                        for each_selected_dialog in dialog_selected:
                            tout.write(each_selected_dialog)
                        feat_selected = x_test_feat[j]
                        for t in range(length_output):
                            string_output = ' '.join([str(data) for data in feat_selected[t]])
                            feat_string = 'TP\t' + string_output + '\n'
                            tfout.write(feat_string)
                        tout.write('\n')
                        tfout.write('\n')



        #Solution model
        concat = Concatenate()([x_pre, x, x_post, attr_result_1, feature_input, attr_result])

        att_prob_solution = Dense(concat.shape[1], activation='sigmoid', name='att_vec')(concat)
        att_mul_solution = Multiply()([concat, att_prob_solution])

        # preds_issue = Dense(len(labels_index), activation='sigmoid', name='issue_dense')(concat)
        preds_answer = Dense(len(labels_index), activation='sigmoid', name='answer_dense')(att_mul_solution)
        model = Model([sequence_input, feature_input, context_input], preds_answer)

        #training
        model.compile(loss='binary_crossentropy',
                      optimizer='adam',
                      metrics=['binary_accuracy'])

        es = EarlyStopping(monitor='val_loss',
                           min_delta=0.0003,
                           patience=5,
                           verbose=0, mode='auto')
        if ios == 1:
            model.summary()
            history = model.fit([x_train_reshape, x_train_feat_with_context_reshape, x_train_with_context_reshape], y_train_reshape,
                                batch_size=8,
                                epochs=1,
                                callbacks=[es],
                                validation_data=([x_val_reshape, x_val_feat_with_context_reshape, x_val_with_context_reshape], y_val_reshape))
            weights_path = '../weights/' + version
            if not os.path.exists(weights_path):
                os.makedirs(weights_path)
            weights = weights_path + '/weights_answer_classification_only.h5'
            model.save_weights(weights, overwrite=True)


            #save fig
            plt.plot(history.history['loss'])
            plt.plot(history.history['val_loss'])
            plt.plot(history.history['val_binary_accuracy'])
            plt.title('model loss')
            plt.ylabel('loss/acc')
            plt.xlabel('epoch')
            plt.legend(['train', 'val', 'val_acc'], loc='upper left')
            # plt.show()

            figname = project + '.png'
            figure_save_path = "../fig_solution/" + version + '/' + project
            if not os.path.exists(figure_save_path):
                os.makedirs(figure_save_path)
            plt.savefig(os.path.join(figure_save_path, figname))
            # plt.draw()
            # plt.pause(6)
            plt.close()



            model.load_weights(weights)
            pred_test = model.predict([x_test_reshape, x_test_feat_with_context_reshape, x_test_with_context_reshape])
        # pred_test = model.predict([x_test_single, x_test_feat_with_context_single, x_test_with_context_single])
        # In[ ]:
        # Prediction and Storage




tout.close()
tfout.close()

for th in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:

    # issue
    if ios == 0:
        from copy import deepcopy
        pred = deepcopy(pred_test)
        pred_issue = pred

        for i in range(pred_issue.shape[0]):
            if len(np.where(pred_issue[i] >= th)[0]) > 0:
                pred_issue[i][pred_issue[i] >= th] = 1
                pred_issue[i][pred_issue[i] < th] = 0
            else:
                max_index = np.argmax(pred_issue[i])
                pred_issue[i] = 0
                pred_issue[i][max_index] = 1
        acc_test = hamming_score(y_test_issue_single, pred_issue)
        p_test, r_test, f1_test = f1(y_test_issue_single, pred_issue)
        print('Answer====>Th: {}, Acc: {}, P: {}, R: {}, F1: {}'.format(th, acc_test, p_test, r_test, f1_test))

    # solution
    if ios == 1:
        from copy import deepcopy
        pred = deepcopy(pred_test)
        pred_answer = pred

        for i in range(pred_answer.shape[0]):
            if len(np.where(pred_answer[i] >= th)[0]) > 0:
                pred_answer[i][pred_answer[i] >= th] = 1
                pred_answer[i][pred_answer[i] < th] = 0
            else:
                max_index = np.argmax(pred_answer[i])
                pred_answer[i] = 0
                pred_answer[i][max_index] = 1
        acc_test = hamming_score(y_test_reshape, pred_answer)
        p_test, r_test, f1_test = f1(y_test_reshape, pred_answer)
        print('Answer====>Th: {}, Acc: {}, P: {}, R: {}, F1: {}'.format(th, acc_test, p_test, r_test, f1_test))



