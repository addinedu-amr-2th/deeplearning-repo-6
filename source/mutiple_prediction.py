import cv2
import numpy as np
import math
from collections import deque
import threading
import numpy as np
from scipy.optimize import linear_sum_assignment
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from keras.models import Sequential
from keras.layers import LSTM, Dense
import keras
import pandas as pd
import queue
import os
import logging
import tensorflow as tf
# 쓰레드 클래스 정의
class FrameProcessingThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super(FrameProcessingThread, self).__init__(*args, **kwargs)
        self.result = None
    def run(self):
        self.result = self._target(*self._args, **self._kwargs)
# 주어진 입력 데이터에서 연속적으로 다음 위치 예측 함수
def predict_next_positions_orange(model, input_data, num_steps):
    current_input = input_data.copy()
    predicted_positions = []
    for _ in range(num_steps):
        predicted = model.predict(current_input, verbose=0)
        predicted_positions.append(predicted[0])
        # 처음 4개 좌표와 예측한 좌표로 새로운 입력 데이터 생성
        new_input = np.concatenate((current_input[:, 1:, :], predicted.reshape(1, 1, -1)), axis=1)
        current_input = new_input
    return np.array(predicted_positions)
# 주어진 입력 데이터에서 연속적으로 다음 위치 예측 함수
def predict_next_positions_red(model, input_data, num_steps):
    current_input = input_data.copy()
    predicted_positions = []
    for _ in range(num_steps):
        predicted = model.predict(current_input, verbose=0)
        predicted_positions.append(predicted[0])
        # 처음 4개 좌표와 예측한 좌표로 새로운 입력 데이터 생성
        new_input = np.concatenate((current_input[:, 1:, :], predicted.reshape(1, 1, -1)), axis=1)
        current_input = new_input
    return np.array(predicted_positions)
def process_frame(frame, position_list_orange, position_list_red, model):
    global t_red
    global t_orange
    global balls_data
    # HSV 색공간으로 변환
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # 주황색 범위를 정의
    # lower_orange = np.array([5, 200, 200])
    # upper_orange = np.array([15, 255, 255])
    lower_orange = np.array([20, 100, 100])
    upper_orange = np.array([30, 255, 255])
    # 빨간색 범위를 정의
    # lower_red = np.array([0, 50, 50])
    # upper_red = np.array([3, 255, 255])
    lower_red = np.array([5, 50, 50])
    upper_red = np.array([15, 255, 255])
    # 주황색 영역을 마스크
    mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)
    # 빨간색 영역을 마스크
    mask_red = cv2.inRange(hsv, lower_red, upper_red)
    # 모폴로지 연산을 사용하여 마스크 개선
    kernel = np.ones((5,5),np.uint8)
    mask_orange = cv2.erode(mask_orange, kernel)
    mask_orange = cv2.dilate(mask_orange, kernel)
    # 모폴로지 연산을 사용하여 마스크 개선
    mask_red = cv2.erode(mask_red, kernel)
    mask_red = cv2.dilate(mask_red, kernel)
    # 윤곽선의 최소 면적을 설정
    min_area = 2000
    # 주황색 윤곽선 추출
    contours_orange, _ = cv2.findContours(mask_orange, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # 가장 큰 주황색 윤곽선을 추출합니다.
    if len(contours_orange) > 0:
        c = max(contours_orange, key=cv2.contourArea)
        area = cv2.contourArea(c)
        if area > min_area:
            x,y,w,h = cv2.boundingRect(c)
            cv2.rectangle(frame,(x,y),(x+w,y+h),(22,100,255),5)
            center_x = x + w//2
            center_y = y + h//2
            position_list_orange,t_orange = return_position_list_orange(frame, position_list_orange, model, w, center_x, center_y,t_orange)
            print('orange'+str(position_list_orange))
    # 빨간색 윤곽선 추출
    contours_red, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # 가장 큰 빨간색 윤곽선을 추출
    if len(contours_red) > 0:
        c = max(contours_red, key=cv2.contourArea)
        area = cv2.contourArea(c)
        if area > min_area:
            x,y,w,h = cv2.boundingRect(c)
            cv2.rectangle(frame,(x,y),(x+w,y+h),(0,30,255),5)
            center_x = x + w//2
            center_y = y + h//2
            position_list_red,t_red = return_position_list_red(frame, position_list_red, model, w, center_x, center_y,t_red)
            print('red'+str(position_list_red))
    # 격자 무늬를 출력
    for i in range(420, 1515, 15):
        cv2.line(frame, (i, 0), (i, 1080), (255, 0, 0), 1)
    for i in range(0, 1095, 15):
        cv2.line(frame, (420, i), (1500, i), (255, 0, 0), 1)
    # 사각형 그리기(측정 영역, 관심 영역)
    # 측정 영역
    cv2.rectangle(frame, (420, 0), (1500, 1080), (0, 255, 0), 3)
    # 관심 영역
    cv2.rectangle(frame, (520, 100), (1400, 980), (0, 255, 255), 3)
    return frame
# 주황공 예측
def return_position_list_orange(frame, position_list_orange, model, w, center_x, center_y,t_orange):
    if center_x > 420 and center_x < 1500:
        cv2.putText(frame, "x: " + str(center_x), (center_x + 10, center_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 4)
        cv2.putText(frame, "y: " + str(center_y), (center_x + 10, center_y + 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 4)
        new_position = [math.ceil((center_x - 420) / 15), math.ceil(center_y / 15)]
        t_orange_t = 0
        if t_orange % 2 == 0:
            t_orange_t = t_orange / 2
            new_position.append(int(t_orange_t))
            position_list_orange.append(new_position)
        t_orange += 1
        # 모델 예측
        if len(position_list_orange) == 5:
            predict_data = np.array(position_list_orange)
            predict_data = predict_data.reshape(1, 5, 3)
            predict_result = predict_next_positions_orange(model, predict_data, 5)
            # marker predict
            for i in range(len(predict_result)-1):
                start_point = ((15*(round(predict_result[i][0])))+420, 15*(round(predict_result[i][1])))
                end_point = ((15*(round(predict_result[i+1][0])))+420, 15*(round(predict_result[i+1][1])))
                pts_xy.append(start_point)
                pts_xy.append(end_point)
            overlay = frame.copy()
            for i in range(0, len(pts_xy), 2):
                start_point = pts_xy[i]
                end_point = pts_xy[i+1]
                if center_x > 520 and center_x < 1400 and center_y > 100 and center_y < 980:
                    cv2.line(overlay, start_point, end_point, (0, 255, 255), thickness=int(w/3))
                # cv2.circle(overlay, end_point, 15, (0, 0, 255), -1)
            alpha = 0.5
            cv2.addWeighted(overlay, alpha, frame, 1-alpha, 0, frame)
            pts_xy.clear()
    else:
        if len(position_list_orange) > 0:
            trajectory_list.append(position_list_orange)
            position_list_orange = deque(maxlen=5)
            t_orange = 0
    if t_orange > 50:
        position_list_orange.clear()
        t_orange = 0
    return position_list_orange,t_orange
# 빨간공 예측
def return_position_list_red(frame, position_list_red, model, w, center_x, center_y,t_red):
    if center_x > 420 and center_x < 1500:
        cv2.putText(frame, "x: " + str(center_x), (center_x + 10, center_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 4)
        cv2.putText(frame, "y: " + str(center_y), (center_x + 10, center_y + 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 4)
        new_position = [math.ceil((center_x - 420) / 15), math.ceil(center_y / 15)]
        t_red_t = 0
        if t_red % 2 == 0:
            t_red_t = t_red/2
            new_position.append(int(t_red_t))
            position_list_red.append(new_position)
        t_red = t_red + 1
        # 모델 예측
        if len(position_list_red) == 5:
            predict_data = np.array(position_list_red)
            predict_data = predict_data.reshape(1, 5, 3)
            predict_result = predict_next_positions_red(model, predict_data, 5)
            # marker predict
            for i in range(len(predict_result)-1):
                start_point = ((15*(round(predict_result[i][0])))+420, 15*(round(predict_result[i][1])))
                end_point = ((15*(round(predict_result[i+1][0])))+420, 15*(round(predict_result[i+1][1])))
                pts_xy.append(start_point)
                pts_xy.append(end_point)
            overlay = frame.copy()
            for i in range(0, len(pts_xy), 2):
                start_point = pts_xy[i]
                end_point = pts_xy[i+1]
                if center_x > 520 and center_x < 1400 and center_y > 100 and center_y < 980:
                    cv2.line(overlay, start_point, end_point, (0, 255, 255), thickness=int(w/3))
                # cv2.circle(overlay, end_point, 15, (0, 0, 255), -1)
            alpha = 0.5
            cv2.addWeighted(overlay, alpha, frame, 1-alpha, 0, frame)
            pts_xy.clear()
    else:
        if len(position_list_red) > 0:
            trajectory_list.append(position_list_red)
            position_list_red = deque(maxlen=5)
            t_red = 0
    if t_red > 50:
        position_list_red.clear()
        t_red = 0
    return position_list_red,t_red
# 모델 로드
model = keras.models.load_model('/Users/kks/Documents/one_day_project/ball_trajectory_prediction/data/first_model.h5', compile=False)
# 카메라 입력
# cap = cv2.VideoCapture(0)
cap  = cv2.VideoCapture('/Users/kks/Documents/one_day_project/ball_trajectory_prediction/data/IMG_9171 2.MOV')
# 궤적 리스트
position_list_orange = deque(maxlen=5)
position_list_red = deque(maxlen=5)
trajectory_list = []
pts_x = []
pts_y = []
pts_xy = []
t_red=0
t_orange=0
balls_data = []
# 메인 루프
while True:
    # 프레임을 읽어옴
    ret, frame = cap.read()
    frame_processing_thread = FrameProcessingThread(target=process_frame, args=(frame, position_list_orange, position_list_red , model))
    frame_processing_thread.start()
    frame_processing_thread.join()
    result_frame = frame_processing_thread.result
    if result_frame is not None:
        cv2.imshow('Orange Ball Tracker', result_frame)
    else:
        print("Error: Result frame is empty.")
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
cap.release()
cv2.destroyAllWindows()