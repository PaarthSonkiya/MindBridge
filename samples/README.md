# Sample recordings for a first run

Synthetic speech made with MindBridge's own voices (Piper, Supertonic-3), so they can be shipped with the
package. Use them to check an installation without a microphone (from `app/`, after
`. .venv/bin/activate`):

```bash
python -m mindbridge file samples/en_machine4_restriction.wav --src en --tgt vi
python -m mindbridge file samples/vi_machine6_vibration.wav samples/vi_can_we_restart.wav --src vi --tgt en
python -m mindbridge file samples/ko_wear_gloves.wav --src ko --tgt vi
```

| File | Language | Text |
|---|---|---|
| en_machine4_restriction.wav | English | Do not restart Machine 4 until the pressure valve is replaced. |
| vi_machine6_vibration.wav | Vietnamese | Máy số 6 lại rung mạnh khi chạy đến tám mươi phần trăm tải. |
| vi_can_we_restart.wav | Vietnamese | Bây giờ có thể khởi động lại máy số 4 chưa? |
| ko_wear_gloves.wav | Korean | 화학 약품 드럼을 다룰 때는 장갑과 보안경을 착용하세요. |

For real human speech, use the organisers' sample set with `bench/run_benchmark.py`.
