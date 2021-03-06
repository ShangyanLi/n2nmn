from __future__ import absolute_import, division, print_function

import numpy as np
import tensorflow as tf
from tensorflow import convert_to_tensor as to_T

from util.cnn import fc_layer as fc, conv_layer as conv

class Modules:
    def __init__(self, image_feat_grid, word_vecs, num_choices):
        self.image_feat_grid = image_feat_grid
        self.word_vecs = word_vecs
        self.num_choices = num_choices

    def _slice_image_feat_grid(self, batch_idx):
        # this callable will be wrapped into a td.Function
        # In TF Fold, batch_idx is a [N_batch, 1] tensor
        res = tf.gather(self.image_feat_grid, batch_idx)
        print('sliced image feat grid dim: {}'.format(res.get_shape()))
        return res

    def _slice_word_vecs(self, time_idx, batch_idx):
        # this callable will be wrapped into a td.Function
        # In TF Fold, batch_idx and time_idx are both [N_batch, 1] tensors
        # time is highest dim in word_vecs
        joint_index = tf.stack([time_idx, batch_idx], axis=1)
        res = tf.gather_nd(self.word_vecs, joint_index)
        print('sliced word vecs dim: {}'.format(res.get_shape()))
        return res

    # All the layers are wrapped with td.ScopedLayer
    def FindModule(self, time_idx, batch_idx, map_dim=500, scope='FindModule',
        reuse=None):
        # In TF Fold, batch_idx and time_idx are both [N_batch, 1] tensors

        image_feat_grid = self._slice_image_feat_grid(batch_idx)
        image_feat_grid_sh = image_feat_grid.get_shape().as_list()
        print('image_feat_grid_sh: ', image_feat_grid_sh)
        image_feat_grid_sh = [i if i else 0 for i in image_feat_grid_sh]
        if image_feat_grid_sh:
            image_feat_grid = tf.Print(image_feat_grid, [tf.constant(image_feat_grid_sh), image_feat_grid], message="This is image_feat_grid: ", summarize=100)
        text_param = self._slice_word_vecs(time_idx, batch_idx)
        text_param_sh = text_param.get_shape().as_list()
        print('text_param_sh: ', text_param_sh)
        text_param_sh = [i if i else 0 for i in text_param_sh]
        if text_param_sh:
            text_param = tf.Print(text_param, [tf.constant(text_param_sh), text_param], message="This is text_param: ", summarize=100)
        # Mapping: image_feat_grid x text_param -> att_grid
        # Input:
        #   image_feat_grid: [N, H, W, D_im]
        #   text_param: [N, D_txt]
        # Output:
        #   att_grid: [N, H, W, 1]
        #
        # Implementation:
        #   1. Elementwise multiplication between image_feat_grid and text_param
        #   2. L2-normalization
        #   3. Linear classification
        with tf.variable_scope(scope, reuse=reuse):
            image_shape = tf.shape(image_feat_grid)
            N = tf.shape(time_idx)[0]
            H = image_shape[1]
            W = image_shape[2]
            D_im = image_feat_grid.get_shape().as_list()[-1]
            D_txt = text_param.get_shape().as_list()[-1]

            print('N: {}\nD_im: {}\nD_txt: {}'.format(N, D_im, D_txt))
            # image_feat_mapped has shape [N, H, W, map_dim]
            image_feat_mapped = _1x1_conv('conv_image', image_feat_grid,
                                          output_dim=map_dim)

            text_param_mapped = fc('fc_text', text_param, output_dim=map_dim)
            text_param_mapped = tf.reshape(text_param_mapped, to_T([N, 1, 1, map_dim]))
            text_param_mapped_sh = text_param_mapped.get_shape().as_list()
            print('text_param_mapped_sh: ', text_param_mapped_sh)
            text_param_mapped_sh = [i if i else 0 for i in text_param_mapped_sh]
            if text_param_mapped_sh:
                text_param_mapped = tf.Print(text_param_mapped, [tf.constant(text_param_mapped_sh), text_param_mapped], message="This is text_param_mapped: ", summarize=100)
            print('Shape of text_param_mapped: {}'.format(text_param_mapped.get_shape()))
            print('Shape of image_feat_mapped: {}'.format(image_feat_mapped.get_shape()))
            eltwise_mult = tf.nn.l2_normalize(image_feat_mapped * text_param_mapped, 3)
            print('Shape of eltwise_mult: {}'.format(eltwise_mult.get_shape()))
            emshape = tf.shape(eltwise_mult)
            ems1 = emshape[1]
            ems1 = tf.Print(ems1, [ems1], message="This is ems1: ")
            ems2 = emshape[2]
            ems2 = tf.Print(ems2, [ems2], message="This is ems2: ")
            ems3 = emshape[3]
            ems3 = tf.Print(ems3, [ems3], message="This is ems3: ")
            ems4 = emshape[4]
            ems4 = tf.Print(ems4, [ems4], message="This is ems4: ")
            att_grid = _1x1_conv('conv_eltwise', eltwise_mult, output_dim=1)
            att_grid_sh = att_grid.get_shape().as_list()
            print('att_grid_sh: ', att_grid_sh)
            att_grid_sh = [i if i else 0 for i in att_grid_sh]
            if att_grid_sh:
                att_grid = tf.Print(att_grid, [tf.constant(att_grid_sh), att_grid], message="This is att_grid: ", summarize=100)
            print('Shape of att_grid: {}'.format(att_grid.get_shape()))

            # TODO
            # Do we need to take exponential over the scores?
            # No.
            # Does the attention needs to be normalized? (sum up to 1)
            # No, since non-existence should be 0 everywhere

        return att_grid

    def TransformModule(self, input_0, time_idx, batch_idx, kernel_size=3,
        map_dim=500, scope='TransformModule', reuse=None):
        # In TF Fold, batch_idx and time_idx are both [N_batch, 1] tensors

        att_grid = input_0
        text_param = self._slice_word_vecs(time_idx, batch_idx)
        # Mapping: att_grid x text_param -> att_grid
        # Input:
        #   att_grid: [N, H, W, 1]
        #   text_param: [N, D_txt]
        # Output:
        #   att_grid_transformed: [N, H, W, 1]
        #
        # Implementation:
        #   Convolutional layer that also involve text_param
        #   A 'soft' convolutional kernel that is modulated by text_param
        with tf.variable_scope(scope, reuse=reuse):
            att_shape = tf.shape(att_grid)
            N = att_shape[0]
            H = att_shape[1]
            W = att_shape[2]
            att_maps = _conv('conv_maps', att_grid, kernel_size=kernel_size,
                stride=1, output_dim=map_dim)

            text_param_mapped = fc('text_fc', text_param, output_dim=map_dim)
            text_param_mapped = tf.reshape(text_param_mapped, to_T([N, 1, 1, map_dim]))

            eltwise_mult = tf.nn.l2_normalize(att_maps * text_param_mapped, 3)
            att_grid = _1x1_conv('conv_eltwise', eltwise_mult, output_dim=1)

        return att_grid

    def AndModule(self, input_0, input_1, time_idx, batch_idx,
        scope='AndModule', reuse=None):
        # In TF Fold, batch_idx and time_idx are both [N_batch, 1] tensors

        att_grid_0 = input_0
        att_grid_1 = input_1
        # Mapping: att_grid x att_grid -> att_grid
        # Input:
        #   att_grid_0: [N, H, W, 1]
        #   att_grid_1: [N, H, W, 1]
        # Output:
        #   att_grid_and: [N, H, W, 1]
        #
        # Implementation:
        #   Take the elementwise-min
        with tf.variable_scope(scope, reuse=reuse):
            att_grid_and = tf.minimum(att_grid_0, att_grid_1)

        return att_grid_and

    def AnswerModule(self, input_0, time_idx, batch_idx,
        scope='AnswerModule', reuse=None):
        # In TF Fold, batch_idx and time_idx are both [N_batch, 1] tensors

        att_grid = input_0
        # Mapping: att_grid -> answer probs
        # Input:
        #   att_grid: [N, H, W, 1]
        # Output:
        #   answer_scores: [N, self.num_choices]
        #
        # Implementation:
        #   1. Max-pool over att_grid
        #   2. a linear mapping layer (without ReLU)
        with tf.variable_scope(scope, reuse=reuse):
            att_shape = tf.shape(att_grid)
            N = att_shape[0]
            H = att_shape[1]
            W = att_shape[2]

            att_min = tf.reduce_min(att_grid, axis=[1, 2])
            att_avg = tf.reduce_mean(att_grid, axis=[1, 2])
            att_max = tf.reduce_max(att_grid, axis=[1, 2])
            # att_reduced has shape [N, 3]
            att_reduced = tf.concat([att_min, att_avg, att_max], axis=1)
            scores = fc('fc_scores', att_reduced, output_dim=self.num_choices)

        return scores


def _1x1_conv(name, bottom, output_dim, reuse=None):
    # TensorFlow Fold can generate zero-size batch for conv layer
    # which will crash cuDNN on backward pass. So use this
    # for 1x1 convolution in modules to avoid the crash.
    bottom_shape = tf.shape(bottom)
    N = bottom_shape[0]
    H = bottom_shape[1]
    W = bottom_shape[2]
    input_dim = bottom.get_shape().as_list()[-1]
    bottom_flat = tf.reshape(bottom, [-1, input_dim])

    # weights and biases variables
    with tf.variable_scope(name, reuse=reuse):
        # initialize the variables
        weights_initializer = tf.contrib.layers.xavier_initializer()
        biases_initializer = tf.constant_initializer(0.)
        weights = tf.get_variable('weights', [input_dim, output_dim],
            initializer=weights_initializer)
        biases = tf.get_variable('biases', output_dim,
            initializer=biases_initializer)

        conv_flat = tf.nn.xw_plus_b(bottom_flat, weights, biases)
        conv = tf.reshape(conv_flat, to_T([N, H, W, output_dim]))
    print('conv output shape: {}'.format(conv.get_shape()))
    return conv

# TensorFlow Fold can generate zero-size batch for conv layer
# which will crash cuDNN on backward pass. So use this
# for arbitrary convolution in modules to avoid the crash.
def _conv(name, bottom, kernel_size, stride, output_dim, padding='SAME',
          bias_term=True, weights_initializer=None,
          biases_initializer=None, reuse=None):
    g = tf.get_default_graph()
    with g.gradient_override_map({'Conv2D': 'Conv2D_handle_empty_batch'}):
        return conv(name, bottom, kernel_size, stride, output_dim,
                    padding, bias_term, weights_initializer,
                    biases_initializer, reuse=reuse)

@tf.RegisterGradient('Conv2D_handle_empty_batch')
def _Conv2DGrad(op, grad):
    with tf.device('/cpu:0'):
        return [tf.nn.conv2d_backprop_input(
                tf.shape(op.inputs[0]), op.inputs[1], grad, op.get_attr('strides'),
                op.get_attr('padding'), op.get_attr('use_cudnn_on_gpu'),
                op.get_attr('data_format')),
                tf.nn.conv2d_backprop_filter(op.inputs[0],
                                             tf.shape(op.inputs[1]), grad,
                                             op.get_attr('strides'),
                                             op.get_attr('padding'),
                                             op.get_attr('use_cudnn_on_gpu'),
                                             op.get_attr('data_format'))]
# def _Conv2DGrad(op, grad):
#     def _input_nonempty():
#         return tf.nn.conv2d_backprop_input(
#             tf.shape(op.inputs[0]), op.inputs[1], grad, op.get_attr('strides'),
#             op.get_attr('padding'), op.get_attr('use_cudnn_on_gpu'),
#             op.get_attr('data_format'))
#     def _filter_nonempty():
#         return tf.nn.conv2d_backprop_filter(op.inputs[0],
#                                             tf.shape(op.inputs[1]), grad,
#                                             op.get_attr('strides'),
#                                             op.get_attr('padding'),
#                                             op.get_attr('use_cudnn_on_gpu'),
#                                             op.get_attr('data_format'))
#     def _input_empty():
#         return tf.zeros_like(op.inputs[0])
#     def _filter_empty():
#         return tf.zeros_like(op.inputs[1])
#     is_nonempty = tf.greater(tf.size(op.inputs[0]), 0)
#     return [tf.cond(is_nonempty, _input_empty, _input_empty),
#             tf.cond(is_nonempty, _filter_empty, _filter_empty)]
