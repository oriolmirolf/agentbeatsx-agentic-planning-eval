(define (problem hospital-p07)
  (:domain hospital)

  (:objects
    p_emerg1 p_emerg2
    p_medA p_medB
    p_old_icu
    - patient

    b_icu1 b_icu2
    b_med1 b_med2
    - bed

    w_icu w_med - ward
  )

  (:init
    ;; Ward requirements
    (patient-ward p_emerg1  w_icu)
    (patient-ward p_emerg2  w_icu)
    (patient-ward p_medA    w_med)
    (patient-ward p_medB    w_med)
    (patient-ward p_old_icu w_icu)

    ;; Beds
    (bed-ward b_icu1 w_icu)
    (bed-ward b_icu2 w_icu)
    (bed-ward b_med1 w_med)
    (bed-ward b_med2 w_med)

    ;; New ICU emergencies waiting
    (waiting p_emerg1)
    (waiting p_emerg2)

    ;; Current occupancy:
    ;; - ICU1: med overflow patient
    ;; - ICU2: old ICU patient (to be discharged)
    ;; - MED1: med patient
    ;; - MED2: dirty and unusable
    (in-bed p_medA    b_icu1)
    (in-bed p_old_icu b_icu2)
    (in-bed p_medB    b_med1)

    (bed-dirty b_med2)

    (= (total-cost) 0)
  )

  ;; Target:
  ;; - Both emergencies in ICU beds
  ;; - Both med patients in med beds
  ;; - Old ICU patient discharged
  (:goal
    (and
      (in-bed p_emerg1  b_icu1)
      (in-bed p_emerg2  b_icu2)
      (in-bed p_medA    b_med1)
      (in-bed p_medB    b_med2)
      (discharged p_old_icu)
    )
  )

  (:metric minimize (total-cost))
)
