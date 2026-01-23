from __future__ import annotations

from pulseox.clean_csv import CleanConfig, clean_a340b_lk_csv_rows


def test_clean_a340b_lk_csv_rows_rededecodes_and_filters() -> None:
    rows = [
        {
            "elapsed_s": "0.0",
            "raw_notification_hex": "f1-5c-46-00-00-00-00",  # 92 / 70
        },
        {
            "elapsed_s": "1.0",
            "raw_notification_hex": "f1-5c-58-00-00-00-00",  # 92 / 88 (spike)
        },
        {
            "elapsed_s": "2.0",
            "raw_notification_hex": "f1-5c-46-00-00-00-00",  # 92 / 70
        },
    ]

    cfg = CleanConfig(
        spo2_min=80,
        spo2_max=100,
        pulse_min=35,
        pulse_max=140,
        max_spo2_dev=6,
        max_pulse_dev=20,
        max_dspo2=4,
        max_dpulse=15,
        ffill_max_age_s=5.0,
    )

    out_rows, stats = clean_a340b_lk_csv_rows(rows, config=cfg)

    assert stats["measurements"] == 3
    assert stats["kept"] == 2
    assert stats["dropped"] == 1

    assert out_rows[0]["spo2_redecoded"] == "92"
    assert out_rows[0]["pulse_redecoded"] == "70"
    assert out_rows[0]["keep"] == "1"
    assert out_rows[0]["spo2_clean"] == "92"
    assert out_rows[0]["pulse_clean"] == "70"

    assert out_rows[1]["spo2_redecoded"] == "92"
    assert out_rows[1]["pulse_redecoded"] == "88"
    assert out_rows[1]["keep"] == "0"
    assert out_rows[1]["drop_reason"] == "pulse_step_too_large"
    # Forward-fill from last kept within ffill window.
    assert out_rows[1]["spo2_clean"] == "92"
    assert out_rows[1]["pulse_clean"] == "70"

    assert out_rows[2]["spo2_redecoded"] == "92"
    assert out_rows[2]["pulse_redecoded"] == "70"
    assert out_rows[2]["keep"] == "1"
    assert out_rows[2]["spo2_clean"] == "92"
    assert out_rows[2]["pulse_clean"] == "70"
