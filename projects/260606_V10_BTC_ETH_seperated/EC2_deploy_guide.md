# EC2 ?œë²„ ??Freqtrade ?€??ë´??œë¸Œê³„ì • ê²©ë¦¬) ?¤ì „ ë°°í¬ ê°€?´ë“œ

ë³?ê°€?´ë“œ??EC2 (Linux/Ubuntu) ?˜ê²½?ì„œ 2ê°œì˜ Freqtrade ë´?BTC 72h / ETH 24h)???œë¡œ ?¤ë¥¸ API Key?€ ?œë¸Œê³„ì • ?”ê³ ë¥??œìš©?˜ì—¬ ê²©ë¦¬ êµ¬ë™?˜ëŠ” ??ê°€ì§€ ë°°í¬ ë°©ì•ˆ???¤ë£¹?ˆë‹¤.

---

## ?“Œ ?„ìˆ˜ ì¤€ë¹??¬í•­
1. **ê±°ë˜??API ?¤ì •**:
   - ?œë¸Œê³„ì • A(BTC???€ ?œë¸Œê³„ì • B(ETH??ë¡??ì‚°??ê°ê° 50%??ë¶„í•  ?´ì²´?©ë‹ˆ??
   - ê°?ê³„ì •?ì„œ **? ë¬¼(Futures) ê±°ë˜**ê°€ ?œì„±?”ëœ API Key?€ Secret Keyë¥?ë°œê¸‰ë°›ìŠµ?ˆë‹¤.
2. **?”ë ˆê·¸ë¨ ì±„ë„ ?¤ì •**:
   - ?”ë ˆê·¸ë¨ ë´?2ê°œë? ê°ê° ?ì„±?˜ì—¬, BTC ê±°ë˜ ëª¨ë‹ˆ?°ë§??? í°ê³?ETH ê±°ë˜ ëª¨ë‹ˆ?°ë§??? í°???•ë³´?©ë‹ˆ??
3. **?¤ì • ?Œì¼ ì¤€ë¹?*:
   - `260606_optimized_project` ?´ì˜ `config_live_btc.json` ë°?`config_live_eth.json` ?Œì¼??API Key?€ ?”ë ˆê·¸ë¨ ?•ë³´ë¥?ê¸°ì…?©ë‹ˆ??

---

## ?³ ë°©ì•ˆ A: Docker Compose ê¸°ë°˜ ?€??ì»¨í…Œ?´ë„ˆ êµ¬ë™ (ê¶Œì¥)
Dockerë¥??¬ìš©?˜ë©´ ?¼ì´ë¸ŒëŸ¬ë¦?ì¶©ëŒ ?†ì´ ?„ë²½??ê²©ë¦¬???˜ê²½?ì„œ ??ë´‡ì„ ê°€?™í•  ???ˆìŠµ?ˆë‹¤.

### 1. `docker-compose.yml` ?Œì¼ ?‘ì„±
EC2 ???„ë¡œ?íŠ¸ ?´ë” ë£¨íŠ¸??`docker-compose.yml` ?Œì¼???ì„±?˜ê³  ?„ë˜ êµ¬ì¡°ë¡??‘ì„±?©ë‹ˆ??

```yaml
version: '3'

services:
  freqtrade_btc:
    image: freqtradeorg/freqtrade:stable
    container_name: freqtrade_live_btc
    volumes:
      - "./user_data:/freqtrade/user_data"
      - "./260606_optimized_project/config_live_btc.json:/freqtrade/config.json"
      - "./260606_optimized_project/config_freqai_bt_btc_72h.json:/freqtrade/config_freqai.json"
    ports:
      - "8080:8080"
    command: >
      trade 
      --strategy V10_BTC_ETH_optimized 
      --config /freqtrade/config.json 
      --config /freqtrade/config_freqai.json
    restart: always

  freqtrade_eth:
    image: freqtradeorg/freqtrade:stable
    container_name: freqtrade_live_eth
    volumes:
      - "./user_data:/freqtrade/user_data"
      - "./260606_optimized_project/config_live_eth.json:/freqtrade/config.json"
      - "./260606_optimized_project/config_freqai_bt_eth_24h.json:/freqtrade/config_freqai.json"
    ports:
      - "8081:8081"
    command: >
      trade 
      --strategy V10_BTC_ETH_optimized 
      --config /freqtrade/config.json 
      --config /freqtrade/config_freqai.json
    restart: always
```

### 2. ê°€??ë°?ëª¨ë‹ˆ?°ë§ ëª…ë ¹??*   **ë°±ê·¸?¼ìš´??ê°€??*:
    ```bash
    docker-compose up -d
    ```
*   **?¤ì‹œê°?ë¡œê·¸ ?•ì¸ (BTC)**:
    ```bash
    docker logs -f freqtrade_live_btc
    ```
*   **?¤ì‹œê°?ë¡œê·¸ ?•ì¸ (ETH)**:
    ```bash
    docker logs -f freqtrade_live_eth
    ```

---

## ?™ï¸ ë°©ì•ˆ B: Systemd ?œë¹„??ê¸°ë°˜ ë¡œì»¬ ê°€??(Docker ë¯¸ì‚¬????
Dockerë¥??¬ìš©?˜ì? ?Šê³  ?Œì´??ê°€?í™˜ê²?`venv`)?ì„œ systemd ?œë¹„?¤ë? ?±ë¡?˜ì—¬ ?Œë¦¬??ë°©ì‹?…ë‹ˆ??

### 1. BTC ë´??œë¹„???±ë¡ (`/etc/systemd/system/freqtrade-btc.service`)
```ini
[Unit]
Description=Freqtrade Live Bot - BTC 72h
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/freqtrade
ExecStart=/home/ubuntu/freqtrade/.venv/bin/freqtrade trade \
  --strategy V10_BTC_ETH_optimized \
  --config /home/ubuntu/freqtrade/260606_optimized_project/config_live_btc.json \
  --config /home/ubuntu/freqtrade/260606_optimized_project/config_freqai_bt_btc_72h.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. ETH ë´??œë¹„???±ë¡ (`/etc/systemd/system/freqtrade-eth.service`)
```ini
[Unit]
Description=Freqtrade Live Bot - ETH 24h
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/freqtrade
ExecStart=/home/ubuntu/freqtrade/.venv/bin/freqtrade trade \
  --strategy V10_BTC_ETH_optimized \
  --config /home/ubuntu/freqtrade/260606_optimized_project/config_live_eth.json \
  --config /home/ubuntu/freqtrade/260606_optimized_project/config_freqai_bt_eth_24h.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. ?œë¹„???œì„±??ë°?ê°€??```bash
# ?°ëª¬ ?¬ë¡œ??sudo systemctl daemon-reload

# ?œë¹„???œì‘ ë°??ì‹œ ?±ë¡
sudo systemctl enable --now freqtrade-btc.service
sudo systemctl enable --now freqtrade-eth.service

# ê°€???íƒœ ?•ì¸
sudo systemctl status freqtrade-btc
sudo systemctl status freqtrade-eth
```

---

## ?’¾ [t3.small ê¶Œì¥] Swap ê°€??ë©”ëª¨ë¦?4GB ?¤ì • ê°€?´ë“œ
T3_small ?¸ìŠ¤?´ìŠ¤(ë¬¼ë¦¬ RAM 2GB) ?˜ê²½?ì„œ 2ê°œì˜ FreqAI ë´‡ì´ ëª¨ë¸???ˆì •?ìœ¼ë¡??¬í•™?µí•˜?„ë¡ ?•ëŠ” ?„ìˆ˜ ë³´ì™„ ?‘ì—…?…ë‹ˆ?? EC2 ?°ë??ì—???¤ìŒ ëª…ë ¹?´ë? ì°¨ë?ë¡??…ë ¥?˜ì‹­?œì˜¤.

```bash
# 1. 4GB ?©ëŸ‰??swap ?Œì¼ ?ì„± (128MB x 32 = 4GB)
sudo dd if=/dev/zero of=/swapfile bs=128M count=32

# 2. swap ?Œì¼ ê¶Œí•œ ?½ê¸°/?°ê¸° ?„ìš© ?œí•œ
sudo chmod 600 /swapfile

# 3. ?Œì¼??swap êµ¬ì—­?¼ë¡œ ?¬ë§·
sudo mkswap /swapfile

# 4. swap êµ¬ì—­ ?œì„±??sudo swapon /swapfile

# 5. ?œë²„ ?¬ë????œì—???ë™?¼ë¡œ ë§ˆìš´?¸ë˜?„ë¡ ?¤ì • ?±ë¡
echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab

# 6. ?œì„±???•ìƒ ?¬ë? ?•ì¸ (Swap ??ª©??4.0G ê°€ ?œì‹œ?˜ì–´????
free -h
```

---

## ?› ï¸??¤ì „ ê°€??ì²´í¬ë¦¬ìŠ¤??1. **ì²?FreqAI ëª¨ë¸ ?™ìŠµ ëª¨ë‹ˆ?°ë§**: ë´‡ì„ ê¸°ë™?˜ë©´ ìµœì´ˆ 1???„ì²´ ?°ì´?°ë? ?™ìŠµ?˜ëŠ” ????10~15ë¶„ì´ ?Œìš”?©ë‹ˆ?? ?™ìŠµ ?œê°„ ?™ì•ˆ ?”ë ˆê·¸ë¨???ëŸ¬ ë©”ì‹œì§€ê°€ ì°íˆì§€ ?Šê³  `model trained successfully` ë¬¸êµ¬ê°€ ì¶œë ¥?˜ëŠ”ì§€ ê°ì‹œ?©ë‹ˆ??
2. **?ˆë²„ë¦¬ì? ?¤ì • ?•ì¸**: ê±°ë˜??UI??ì§ì ‘ ë¡œê·¸?¸í•˜?????œë¸Œê³„ì •???ˆë²„ë¦¬ì?ê°€ ê°ê° ìµœì ??ê²°ê³¼??ë§ê²Œ ê°•ì œ ?œí•œ?˜ì—ˆ?”ì? ?•ì¸?©ë‹ˆ??(BTC ë¡?14ë°???6ë°? ETH ë¡?12ë°???9ë°?.
3. **Isolated Margin(ê²©ë¦¬ ë§ˆì§„) ?•ì¸**: ? ë¬¼ ê³„ì •???¬ë¡œ??Cross) ëª¨ë“œê°€ ?„ë‹Œ **ê²©ë¦¬(Isolated)** ëª¨ë“œë¡??‹ì—…?˜ì–´ ?ˆëŠ”ì§€ ì²´í¬?˜ì—¬ ë¶ˆí•„?”í•œ ì¦ê±°ê¸?? ì‹??ì² ì???ë°©ì??©ë‹ˆ??
