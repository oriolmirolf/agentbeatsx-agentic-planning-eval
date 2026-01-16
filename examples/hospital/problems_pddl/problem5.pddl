(define (problem hospital-p05)
  (:domain hospital)

  (:objects
    p_emerg1 p_emerg2      ; new ICU emergencies
    p_iso                   ; new isolation patient
    p_medA p_medB           ; med patients that must end in med beds
    p_old_icu               ; legacy ICU patient to be discharged
    - patient

    b_icu1 b_icu2           ; ICU beds
    b_med1 b_med2 b_iso     ; med beds (b_iso is isolation bed)
    - bed

    w_icu w_med - ward
  )

  (:init
    ;; Ward requirements
    (patient-ward p_emerg1  w_icu)
    (patient-ward p_emerg2  w_icu)
    (patient-ward p_iso     w_med)
    (patient-ward p_medA    w_med)
    (patient-ward p_medB    w_med)
    (patient-ward p_old_icu w_icu)

    ;; Beds
    (bed-ward b_icu1 w_icu)
    (bed-ward b_icu2 w_icu)
    (bed-ward b_med1 w_med)
    (bed-ward b_med2 w_med)
    (bed-ward b_iso  w_med)

    ;; Isolation
    (isolation-required p_iso)
    (isolation-bed b_iso)

    ;; Waiting new arrivals
    (waiting p_emerg1)
    (waiting p_emerg2)
    (waiting p_iso)

    ;; Current occupancy:
    ;; - ICU1: med patient overflowing into ICU
    ;; - ICU2: old ICU patient to discharge
    ;; - ISO: non-iso med patient occupying isolation bed
    (in-bed p_medA    b_icu1)
    (in-bed p_old_icu b_icu2)
    (in-bed p_medB    b_iso)

    ;; All regular med beds are dirty (no clean med capacity)
    (bed-dirty b_med1)
    (bed-dirty b_med2)

    (= (total-cost) 0)
  )

  ;; Target:
  ;; - Both emergencies in ICU beds
  ;; - Isolation patient in the isolation bed
  ;; - Med patients in the regular med beds
  ;; - Old ICU patient discharged
  (:goal
    (and
      (in-bed p_emerg1  b_icu1)
      (in-bed p_emerg2  b_icu2)
      (in-bed p_iso     b_iso)
      (in-bed p_medA    b_med1)
      (in-bed p_medB    b_med2)
      (discharged p_old_icu)
    )
  )

  (:metric minimize (total-cost))
)
