# RTP Video Streaming - HD Video Support

## Vấn đề ban đầu

Khi streaming video HD (1920x1080) qua RTP/UDP, video không hiển thị mặc dù:
- Video SD (384x288) chạy tốt
- SeqNum vẫn tăng bình thường
- Không có lỗi rõ ràng

## Nguyên nhân

### 1. Frame HD bị chia thành nhiều packets
- Video SD: 1 frame ≈ 6KB → 1 packet
- Video HD: 1 frame ≈ 249KB → **~178 packets** (MTU = 1400 bytes)

### 2. Packets đến không theo thứ tự
Với UDP, packets có thể đến không đúng sequence:
```
Gửi: 100, 101, 102, 103, 104, 105
Nhận: 100, 102, 101, 105, 103, 104
```

### 3. Logic cũ có bug
Code cũ cập nhật `packetNbr` sau **mỗi packet**:
```python
if currPacketNbr > self.packetNbr:
    buffer.append(packet)
    self.packetNbr = currPacketNbr  # ← BUG!
```

**Vấn đề:** Nếu packet 105 đến trước → `packetNbr = 105` → packets 101-104 đến sau bị reject → frame thiếu data → corrupt!

### 4. Packets cũ lẫn vào frame mới
- Frame 1 kết thúc ở packet 178 (marker=1)
- Packet 150 (của frame 1) đến muộn
- Bị thêm vào buffer của **frame 2** → frame 2 bị corrupt!

## Giải pháp

### Client.py

**1. Track packet cuối của frame trước**
```python
self.lastFramePacket = 0  # Thay vì self.packetNbr
```

**2. Chỉ nhận packets MỚI hơn frame trước**
```python
if currPacketNbr > self.lastFramePacket:
    self.fragmentBuffer.append((currPacketNbr, rtpPacket.getPayload()))

    if marker == 1:  # Frame kết thúc
        self.fragmentBuffer.sort(key = lambda x: x[0])  # Sắp xếp lại đúng thứ tự
        frame = b''.join([f[1] for f in self.fragmentBuffer])
        self.updateMovie(self.writeFrame(frame))

        self.lastFramePacket = currPacketNbr  # Cập nhật SAU KHI frame hoàn chỉnh
        self.fragmentBuffer.clear()
```

**Logic:**
- Chỉ cập nhật `lastFramePacket` khi nhận được **marker=1** (frame hoàn chỉnh)
- Packets cũ đến muộn bị bỏ qua → không lẫn vào frame mới
- Sort buffer trước khi ghép → đúng thứ tự dù nhận không theo thứ tự

**3. Tăng UDP receive buffer**
```python
self.rtpSocket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2097152)  # 2MB
```
Giảm packet loss do buffer tràn khi nhận nhiều packets liên tục.

### ServerWorker.py

**1. Loop video khi hết**
```python
if data:
    self.split_frame(data, address, port)
else:
    # Loop video
    self.clientInfo['videoStream'].file.seek(0)
```

**2. Giữ nguyên delay giữa frames**
```python
self.clientInfo['event'].wait(0.05)  # 20 FPS
```

## Kết quả

- ✅ Video HD (1920x1080) hiển thị mượt mà
- ✅ Video SD (384x288) vẫn chạy tốt như cũ
- ✅ Tự động loop video khi hết
- ✅ Xử lý packets đến không theo thứ tự
- ✅ Ngăn packets cũ lẫn vào frame mới

## Cách chạy

```bash
# Terminal 1: Start server
python Server.py 5000

# Terminal 2: Start client
python Client.py 127.0.0.1 5000 25000 sample.mjpeg
```

## Tuning hiệu năng

### Tăng tốc video
Giảm delay trong `ServerWorker.py`:
```python
self.clientInfo['event'].wait(0.03)  # 33 FPS
self.clientInfo['event'].wait(0.02)  # 50 FPS
```

### Giảm packet loss (nếu cần)
Thêm delay giữa packets trong `ServerWorker.py`:
```python
time.sleep(0.00005)  # 50 microseconds
```

## Tóm tắt thay đổi

### Client.py
- Line 36: `self.lastFramePacket = 0`
- Line 108-118: Logic nhận packets mới (chỉ nhận packets > lastFramePacket, sort buffer, cập nhật sau marker=1)
- Line 281: `setsockopt(socket.SO_RCVBUF, 2097152)`

### ServerWorker.py
- Line 149-151: Loop video khi hết frames

**Tổng cộng: 4 thay đổi nhỏ, fix được vấn đề HD video!**
