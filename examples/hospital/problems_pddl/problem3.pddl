(define (problem hospital-p03)
  (:domain hospital)

  (:objects
    p1 - patient
    b_icu b_med - bed
    w_icu w_med - ward
  )

  (:init
    (patient-ward p1 w_icu)

    ;; UNSOLVABLE MODIFICATION: 
    ;; The only available bed 'b_icu' is now incorrectly zoned as a 'w_med' bed.
    ;; p1 needs w_icu, so they cannot use b_icu.
    (bed-ward b_icu w_med) ;; Was w_icu
    (bed-ward b_med w_med)

    (in-bed p1 b_med)   ; currently in wrong ward
    (bed-free b_icu)

    (= (total-cost) 0)
  )

  (:goal
    (and
      (in-bed p1 b_icu)
    )
  )

  (:metric minimize (total-cost))
)