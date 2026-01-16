(define (problem hospital-p10)
  (:domain hospital)

  (:objects
    p_emerg1 p_emerg2          ; new ICU emergencies
    p_iso                       ; new isolation patient
    p_stable1                   ; med patient that must stay on med1
    p_overflow                  ; med patient currently overflowing into ICU2
    p_old_icu p_old_med         ; legacy ICU + med patients to clear
    - patient

    b_icu1 b_icu2               ; ICU beds
    b_med1 b_med2 b_med_iso     ; med beds (b_med_iso is isolation)
    - bed

    w_icu w_med - ward
  )

  (:init
    ;; Ward requirements
    (patient-ward p_emerg1  w_icu)
    (patient-ward p_emerg2  w_icu)
    (patient-ward p_iso     w_med)
    (patient-ward p_stable1 w_med)
    (patient-ward p_overflow w_med)
    (patient-ward p_old_icu w_icu)
    (patient-ward p_old_med w_med)

    ;; Beds
    (bed-ward b_icu1    w_icu)
    (bed-ward b_icu2    w_icu)
    (bed-ward b_med1    w_med)
    (bed-ward b_med2    w_med)
    (bed-ward b_med_iso w_med)

    ;; Isolation
    (isolation-required p_iso)
    (isolation-bed b_med_iso)

    ;; Waiting new arrivals
    (waiting p_emerg1)
    (waiting p_emerg2)
    (waiting p_iso)

    ;; Current occupancy:
    ;; - ICU1: old ICU patient to discharge
    ;; - ICU2: med overflow patient that must end in med2
    ;; - MED1: stable med patient that must stay there
    ;; - MED2: old med patient to discharge
    (in-bed p_old_icu  b_icu1)
    (in-bed p_overflow b_icu2)
    (in-bed p_stable1  b_med1)
    (in-bed p_old_med  b_med2)

    ;; Isolation bed exists but is dirty
    (bed-dirty b_med_iso)

    (= (total-cost) 0)
  )

  ;; Target:
  ;; - Both emergencies in ICU beds
  ;; - Isolation patient in the isolation bed
  ;; - Stable med patient still on med1
  ;; - Overflow med patient relocated to med2
  ;; - Old ICU and med patients discharged
  (:goal
    (and
      (in-bed p_emerg1  b_icu1)
      (in-bed p_emerg2  b_icu2)
      (in-bed p_iso     b_med_iso)
      (in-bed p_stable1 b_med1)
      (in-bed p_overflow b_med2)
      (discharged p_old_icu)
      (discharged p_old_med)
    )
  )

  (:metric minimize (total-cost))
)
