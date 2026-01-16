(define (problem hospital-p02)
  (:domain hospital)

  (:objects
    p1 - patient
    b1 b2 - bed
    w_med - ward
  )

  (:init
    (patient-ward p1 w_med)

    (bed-ward b1 w_med)
    (bed-ward b2 w_med)

    (waiting p1)

    (bed-dirty b1)     ; needs cleaning
    (bed-blocked b2)   ; unusable here

    (= (total-cost) 0)
  )

  (:goal
    (and
      (in-bed p1 b1)
    )
  )

  (:metric minimize (total-cost))
)
