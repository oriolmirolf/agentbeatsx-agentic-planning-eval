(define (problem hospital-p09)
  (:domain hospital)

  (:objects
    p1 p2 p3 - patient
    b1 b2 b3 - bed
    w_med - ward
  )

  (:init
    (patient-ward p1 w_med)
    (patient-ward p2 w_med)
    (patient-ward p3 w_med)

    (bed-ward b1 w_med)
    (bed-ward b2 w_med)
    (bed-ward b3 w_med)

    ;; Current occupancy
    (in-bed p1 b1)
    (in-bed p2 b2)

    ;; Third bed is blocked and dirty (needs two steps before use)
    (bed-blocked b3)
    (bed-dirty   b3)

    ;; New patient waiting
    (waiting p3)

    (= (total-cost) 0)
  )

  ;; Target:
  ;; - p1 stays in b1
  ;; - p2 moved into b3
  ;; - p3 admitted into b2
  (:goal
    (and
      (in-bed p1 b1)
      (in-bed p2 b3)
      (in-bed p3 b2)
    )
  )

  (:metric minimize (total-cost))
)
