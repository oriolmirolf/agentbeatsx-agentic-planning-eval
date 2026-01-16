(define (problem loadbalance-p04)
  (:domain loadbalance)

  (:objects
    eu_west - region
    web - service
    s1_eu s2_eu s3_eu - server
    b1 b2 b3 b4 - bucket
  )

  (:init
    (= (total-cost) 0)
    (server-region s1_eu eu_west)
    (server-region s2_eu eu_west)
    (server-region s3_eu eu_west)

    (bucket-region b1 eu_west)
    (bucket-region b2 eu_west)
    (bucket-region b3 eu_west)
    (bucket-region b4 eu_west)

    (bucket-service b1 web)
    (bucket-service b2 web)
    (bucket-service b3 web)
    (bucket-service b4 web)

    (online s1_eu)
    (online s2_eu)
    (not (online s3_eu))

    (runs s1_eu web)
    (runs s2_eu web)

    (assigned-to b1 s1_eu)
    (assigned-to b2 s1_eu)
    (assigned-to b3 s2_eu)
    (assigned-to b4 s2_eu)

    ;; capacities 2 each
    (= (capacity s1_eu) 2)
    (= (capacity s2_eu) 2)
    (= (capacity s3_eu) 2)

    (= (load s1_eu) 2)
    (= (load s2_eu) 2)
    (= (load s3_eu) 0)
  )

  ;; Canonical goal: b1,b2 on s1_eu; b3,b4 on s3_eu; s2_eu powered off
  (:goal
    (and
      (assigned-to b1 s1_eu)
      (assigned-to b2 s1_eu)
      (assigned-to b3 s3_eu)
      (assigned-to b4 s3_eu)
      (online s1_eu)
      (online s3_eu)
      (not (online s2_eu))
    )
  )

  (:metric minimize (total-cost))
)