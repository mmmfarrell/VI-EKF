import csv
import numpy as np
import glob, os, sys
sys.path.append('/usr/local/lib/python2.7/site-packages')
import cv2
from tqdm import tqdm
from pyquat import Quaternion
import yaml

R_NWU_NED = np.array([[1, 0, 0],
                      [0, -1, 0],
                      [0, 0, -1]])
R_IMU = np.array([[0, 0, 1],
                  [0, 1, 0],
                  [-1, 0, 0]])

def load_from_file(filename):
    data = np.load(filename)
    return data.item()

def save_to_file(filename, data):
    np.save(filename, data)


def make_undistort_funtion(intrinsics, resolution, distortion_coefficients):
    A = np.array([[float(intrinsics[0]), 0., float(intrinsics[2])], [0., float(intrinsics[1]), float(intrinsics[3])], [0., 0., 1.]])
    Ap, _ = cv2.getOptimalNewCameraMatrix(A, distortion_coefficients, (resolution[0], resolution[1]), 1.0)

    def undistort(image):
        return cv2.undistort(image, A, distortion_coefficients, None, Ap)

    return undistort

def load_data(folder, show_image=False, start=0, end=-1):
    # First, load IMU data
    print "reading imu"
    csvfile = open(folder+'/imu0/data.csv', 'rb')
    imu_data = []
    reader = csv.reader(csvfile)
    for i, row in tqdm(enumerate(reader)):
        if i > 0:
            imu_data.append([float(item) for item in row])
    imu_data = np.array(imu_data)

    # rotate IMU data into the NED frame\
    q_IMU = Quaternion([0.5, 0.5, 0.5, 0.5])
    for row in imu_data:
        row[1:4] = q_IMU.rotate(row[1:4])
        row[4:7] = q_IMU.rotate(row[4:7])

    t0 = imu_data[0,0]
    imu_data[:,0] -= t0
    imu_data[:,0] /= 1e9

    # Load Camera Data
    images0 = []
    images1 = []
    image_time = []
    csvfile = open(folder + '/cam0/data.csv', 'rb')
    reader = csv.reader(csvfile)
    print "reading images"
    for i, row in tqdm(enumerate(reader)):
        if i > 0:
            image_time.append((float(row[0]) - t0) / 1e9)
            images0.append(folder + '/cam0/data/' + row[1])
            images1.append(folder + '/cam1/data/' + row[1])
            if show_image:
                cv2.imshow('image', cv2.imread(folder+'/cam0/data/' + row[1]))
                print image_time[-1]
                #cv2.waitKey(0)
    image_time = np.array(image_time)
    # images = np.array(images)

    # Load ground truth estimate
    ground_truth = []
    csvfile = open(folder + '/state_groundtruth_estimate0/data.csv', 'rb')
    reader = csv.reader(csvfile)
    print "reading truth"
    for i, row in tqdm(enumerate(reader)):
        if i > 0:
            ground_truth.append([float(item) for item in row])
    ground_truth = np.array(ground_truth)
    ground_truth[:,0] -= t0
    ground_truth[:,0] /= 1e9

    # rotate ground_truth into the right frame

    for row in ground_truth:
        row[1:4] = R_NWU_NED.dot(row[1:4])
        row[4:8] = q_IMU * Quaternion(row[4:8]).elements
        row[8:11] = R_NWU_NED.dot(row[8:11])
        row[11:14] = q_IMU.rotate(row[11:14])
        row[14:17] = q_IMU.rotate(row[14:17])

    # chop data
    imu_data = imu_data[imu_data[:,0] > start, :]
    images0 = [f for f, t in zip(images0, image_time > start) if t]
    images1 = [f for f, t in zip(images1, image_time > start) if t]
    image_time = image_time[image_time > start]
    ground_truth = ground_truth[ground_truth[:, 0] > start, :]

    if end > start:
        imu_data = imu_data[imu_data[:, 0] < end, :]
        ground_truth = ground_truth[ground_truth[:, 0] < end, :]
        images0 = [f for f, t in zip(images0, image_time < end) if t]
        images1 = [f for f, t in zip(images1, image_time < end) if t]
        image_time = image_time[image_time < end]

    print "done reading data"

    with open(folder + '/cam0/sensor.yaml', 'r') as stream:
        try:
            data = yaml.load(stream)

            print(data['intrinsics'])
            cam0_sensor = {
                'resolution': np.array(data['resolution']),
                'intrinsics': np.array(data['intrinsics']),
                'rate_hz': data['rate_hz'],
                'distortion_coefficients': np.array(data['distortion_coefficients']),
                'body_to_sensor_transform': np.array(data['T_BS']['data']).reshape((data['T_BS']['rows'],data['T_BS']['cols']))
            }


        except yaml.YAMLError as exc:
            print(exc)

    with open(folder + '/cam1/sensor.yaml', 'r') as stream:
        try:
            data = yaml.load(stream)
            cam1_sensor = {
                'resolution': data['resolution'],
                'intrinsics': data['intrinsics'],
                'rate_hz': data['rate_hz'],
                'distortion_coefficients': np.array(data['distortion_coefficients']),
                'body_to_sensor_transform': np.array(data['T_BS']['data']).reshape((data['T_BS']['rows'],data['T_BS']['cols']))
            }

        except yaml.YAMLError as exc:
            print(exc)

    out_dict = dict()
    out_dict['imu'] = imu_data
    out_dict['cam0_sensor'] = cam0_sensor
    out_dict['cam1_sensor'] = cam1_sensor
    out_dict['cam0_frame_filenames'] = images0
    out_dict['cam1_frame_filenames'] = images1
    out_dict['cam_time'] = image_time
    out_dict['truth'] = ground_truth
    return out_dict



if __name__ == '__main__':
    data = load_data('/mnt/pccfs/not_backed_up/eurocmav/mav0', show_image=True)
    save_to_file('/mnt/pccfs/not_backed_up/eurocmav/mav0/data.npy', data)
    print "done"