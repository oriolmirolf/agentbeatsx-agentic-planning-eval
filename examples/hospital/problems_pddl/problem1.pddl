(define (problem hospital-p01)
  (:domain hospital)

  (:objects
    p1 p2 - patient
    b1 b2 - bed
    w_med - ward
  )

  (:init
    (patient-ward p1 w_med)
    (patient-ward p2 w_med)

    (bed-ward b1 w_med)
    (bed-ward b2 w_med)

    (waiting p1)
    (waiting p2)

    (bed-free b1)
    (bed-free b2)

    (= (total-cost) 0)
  )

  (:goal
    (and
      (in-bed p1 b1)
      (in-bed p2 b2)
    )
  )

  (:metric minimize (total-cost))
)
