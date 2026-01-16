(define (problem hospital-p04)
  (:domain hospital)

  (:objects
    p_emerg p_medA p_medB - patient
    b_icu1 b_med1 b_med2 - bed
    w_icu w_med - ward
  )

  (:init
    ;; Ward requirements
    (patient-ward p_emerg w_icu)
    (patient-ward p_medA  w_med)
    (patient-ward p_medB  w_med)

    ;; Beds
    (bed-ward b_icu1 w_icu)
    (bed-ward b_med1 w_med)
    (bed-ward b_med2 w_med)

    ;; One med bed is dirty (potential slack)
    (bed-dirty b_med2)

    ;; Current occupancy
    (in-bed p_medA b_icu1)   ; med patient overflowing into ICU
    (in-bed p_medB b_med1)

    ;; New ICU emergency waiting
    (waiting p_emerg)

    (= (total-cost) 0)
  )

  ;; Target:
  ;; - Emergency in ICU
  ;; - Both med patients in med beds (A in b_med1, B in b_med2)
  (:goal
    (and
      (in-bed p_emerg b_icu1)
      (in-bed p_medA  b_med1)
      (in-bed p_medB  b_med2)
    )
  )

  (:metric minimize (total-cost))
)
