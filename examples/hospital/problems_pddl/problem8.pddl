(define (problem hospital-p08)
  (:domain hospital)

  (:objects
    p_icu1 p_icu2
    p_surg1
    p_med1 p_med2
    - patient

    b_icu1 b_icu2
    b_surg1
    b_med1 b_med2
    - bed

    w_icu w_surg w_med - ward
  )

  (:init
    ;; Ward requirements
    (patient-ward p_icu1 w_icu)
    (patient-ward p_icu2 w_icu)
    (patient-ward p_surg1 w_surg)
    (patient-ward p_med1 w_med)
    (patient-ward p_med2 w_med)

    ;; Beds
    (bed-ward b_icu1  w_icu)
    (bed-ward b_icu2  w_icu)
    (bed-ward b_surg1 w_surg)
    (bed-ward b_med1  w_med)
    (bed-ward b_med2  w_med)

    ;; Current occupancy (messy multi-ward overflow):
    ;; - ICU1: correct ICU patient
    ;; - SURG1: ICU overflow
    ;; - MED1: surgical overflow
    ;; - MED2: correct med patient
    (in-bed p_icu1  b_icu1)
    (in-bed p_icu2  b_surg1)
    (in-bed p_surg1 b_med1)
    (in-bed p_med1  b_med2)

    ;; Extra med patient waiting
    (waiting p_med2)

    ;; Spare ICU2 exists but is dirty; likewise MED2 will need to be freed, then reused.
    (bed-dirty b_icu2)

    (= (total-cost) 0)
  )

  ;; Target:
  ;; - ICU patients in ICU beds
  ;; - Surgical patient in surgical bed
  ;; - Both med patients in med beds
  (:goal
    (and
      (in-bed p_icu1  b_icu1)
      (in-bed p_icu2  b_icu2)
      (in-bed p_surg1 b_surg1)
      (in-bed p_med1  b_med1)
      (in-bed p_med2  b_med2)
    )
  )

  (:metric minimize (total-cost))
)
