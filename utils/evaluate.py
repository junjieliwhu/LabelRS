# coding=utf-8

import numpy as np
import cv2

def calculate(groundTruth,predict):
    groundTruth = groundTruth.astype(np.int16)
    predict = predict.astype(np.int16)
    seg_inv, gt_inv = np.logical_not(predict), np.logical_not(groundTruth)
    true_pos = float(np.logical_and(groundTruth, predict).sum())
    true_neg = np.logical_and(seg_inv, gt_inv).sum()
    false_pos = np.logical_and(predict, gt_inv).sum()
    false_neg = np.logical_and(seg_inv, groundTruth).sum()
    prec = true_pos / (true_pos + false_pos + 1e-6)
    rec = true_pos / (true_pos + false_neg + 1e-6)
    accuracy = (true_pos + true_neg) / (true_pos + true_neg + false_pos + false_neg + 1e-6)
    F1 = 2 * true_pos / (2 * true_pos + false_pos + false_neg + 1e-6)
    IoU = true_pos / (true_pos + false_neg + false_pos + 1e-6)
    print('pre:'+str(prec)+'\t'+'recall:'+str(rec)+'\t'+'accuracy:'+str(accuracy)+'\t'+'F1:'+str(F1)+'\t'+'IoU:'+str(IoU))
    return [prec, rec, accuracy, F1, IoU]


if __name__ == "__main__":

    predict_path=''
    label_path=''
    predict_img = cv2.imread(predict_path)
    label_img = cv2.imread(label_path)
    prec, rec, accuracy, F1, IoU = calculate(predict_img, label_img)



