(define (problem loadbalance-p03)
  (:domain loadbalance)

  (:objects
    ap_south - region
    analytics search - service
    s1_ap - server
    b1 b2 - bucket
  )

  (:init
    (= (total-cost) 0)
    (server-region s1_ap ap_south)

    (bucket-region b1 ap_south)
    (bucket-region b2 ap_south)

    (bucket-service b1 analytics)
    (bucket-service b2 search)

    (online s1_ap)

    ;; Initially only search is running
    (runs s1_ap search)

    (unassigned b1)
    (unassigned b2)

    ;; UNSOLVABLE MODIFICATION: Capacity reduced from 3 to 1
    ;; Goal requires putting b1 AND b2 (2 items) here.
    (= (capacity s1_ap) 1)
    (= (load s1_ap) 0)
  )

  (:goal
    (and
      (assigned-to b1 s1_ap)
      (assigned-to b2 s1_ap)
    )
  )

  (:metric minimize (total-cost))
)