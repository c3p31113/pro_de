import time
import RPi.GPIO as GPIO

# --- GPIOピン設定 ---
Motor_A_EN    = 4
Motor_B_EN    = 17
Motor_A_Pin1  = 14
Motor_A_Pin2  = 15
Motor_B_Pin1  = 27
Motor_B_Pin2  = 18

# --- 定数 ---
Dir_forward   = 0
Dir_backward  = 1
left_forward  = 0
left_backward = 1
right_forward = 0
right_backward= 1

# --- グローバル変数 ---
pwm_A = 0
pwm_B = 0

def motorStop():
    """モーターを停止する"""
    GPIO.output(Motor_A_Pin1, GPIO.LOW)
    GPIO.output(Motor_A_Pin2, GPIO.LOW)
    GPIO.output(Motor_B_Pin1, GPIO.LOW)
    GPIO.output(Motor_B_Pin2, GPIO.LOW)
    GPIO.output(Motor_A_EN, GPIO.LOW)
    GPIO.output(Motor_B_EN, GPIO.LOW)

def setup():
    """モーターの初期化処理"""
    global pwm_A, pwm_B
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(Motor_A_EN, GPIO.OUT)
    GPIO.setup(Motor_B_EN, GPIO.OUT)
    GPIO.setup(Motor_A_Pin1, GPIO.OUT)
    GPIO.setup(Motor_A_Pin2, GPIO.OUT)
    GPIO.setup(Motor_B_Pin1, GPIO.OUT)
    GPIO.setup(Motor_B_Pin2, GPIO.OUT)
    motorStop()
    try:
        pwm_A = GPIO.PWM(Motor_A_EN, 1000)
        pwm_B = GPIO.PWM(Motor_B_EN, 1000)
    except:
        pass

def motor_left(status, direction, speed):
    """左モーターの制御"""
    if status == 0: # 停止
        GPIO.output(Motor_B_Pin1, GPIO.LOW)
        GPIO.output(Motor_B_Pin2, GPIO.LOW)
        GPIO.output(Motor_B_EN, GPIO.LOW)
    else:
        if direction == Dir_backward:
            GPIO.output(Motor_B_Pin1, GPIO.HIGH)
            GPIO.output(Motor_B_Pin2, GPIO.LOW)
            pwm_B.start(100)
            pwm_B.ChangeDutyCycle(speed)
        elif direction == Dir_forward:
            GPIO.output(Motor_B_Pin1, GPIO.LOW)
            GPIO.output(Motor_B_Pin2, GPIO.HIGH)
            pwm_B.start(0)
            pwm_B.ChangeDutyCycle(speed)

def motor_right(status, direction, speed):
    """右モーターの制御"""
    if status == 0: # 停止
        GPIO.output(Motor_A_Pin1, GPIO.LOW)
        GPIO.output(Motor_A_Pin2, GPIO.LOW)
        GPIO.output(Motor_A_EN, GPIO.LOW)
    else:
        if direction == Dir_forward:
            GPIO.output(Motor_A_Pin1, GPIO.HIGH)
            GPIO.output(Motor_A_Pin2, GPIO.LOW)
            pwm_A.start(100)
            pwm_A.ChangeDutyCycle(speed)
        elif direction == Dir_backward:
            GPIO.output(Motor_A_Pin1, GPIO.LOW)
            GPIO.output(Motor_A_Pin2, GPIO.HIGH)
            pwm_A.start(0)
            pwm_A.ChangeDutyCycle(speed)

def move(speed, direction, turn, radius=0.6):
    """ローバーの動作を制御するメイン関数"""
    if direction == 'forward':
        if turn == 'left':
            motor_left(1, left_backward, speed)
            motor_right(0, right_forward, int(speed*radius))
        elif turn == 'right':
            motor_left(0, left_forward, int(speed*radius))
            motor_right(1, right_backward, speed)
        else: # 直進
            motor_left(1, left_backward, speed)
            motor_right(1, right_backward, speed)
    elif direction == 'backward':
        if turn == 'left':
            motor_left(1, left_forward, speed)
            motor_right(0, right_backward, int(speed*radius))
        elif turn == 'right':
            motor_left(0, left_backward, int(speed*radius))
            motor_right(1, right_forward, speed)
        else: # 直進
            motor_left(1, left_forward, speed)
            motor_right(1, right_forward, speed)
    elif direction == 'no': # 旋回
        if turn == 'left':
            motor_left(1, left_forward, speed)
            motor_right(1, right_backward, speed)
        elif turn == 'right':
            motor_left(1, left_backward, speed)
            motor_right(1, right_forward, speed)
        else:
            motorStop()
    else:
        motorStop()

def destroy():
    """終了処理"""
    motorStop()
    GPIO.cleanup()