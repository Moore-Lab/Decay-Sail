import h5py
import numpy as np
import nds2

yaw_channel = 'Y1:RDS-LES_YAW_MON_OUT_DQ'
conn = nds2.connection ('cymac1', 8080)
conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')

