(define (problem loadbalance-p07)
  (:domain loadbalance)

  (:objects
    eu_central - region
    web - service
    s1_eu s2_eu s3_eu - server
    b1 b2 b3 b4 b5 - bucket
  )

  (:init
    (= (total-cost) 0)
    (server-region s1_eu eu_central)
    (server-region s2_eu eu_central)
    (server-region s3_eu eu_central)

    (bucket-region b1 eu_central)
    (bucket-region b2 eu_central)
    (bucket-region b3 eu_central)
    (bucket-region b4 eu_central)
    (bucket-region b5 eu_central)

    (bucket-service b1 web)
    (bucket-service b2 web)
    (bucket-service b3 web)
    (bucket-service b4 web)
    (bucket-service b5 web)

    (online s1_eu)
    (online s2_eu)
    (online s3_eu)

    (runs s1_eu web)
    (runs s2_eu web)
    (runs s3_eu web)

    (assigned-to b1 s1_eu)
    (assigned-to b2 s1_eu)
    (assigned-to b3 s1_eu)
    (assigned-to b4 s2_eu)
    (assigned-to b5 s3_eu)

    (= (capacity s1_eu) 3)
    (= (capacity s2_eu) 3)
    (= (capacity s3_eu) 3)

    (= (load s1_eu) 3)
    (= (load s2_eu) 1)
    (= (load s3_eu) 1)
  )

  ;; Goal: drain s3_eu and power it off; canonical distribution keeps others
  (:goal
    (and
      (assigned-to b1 s1_eu)
      (assigned-to b2 s1_eu)
      (assigned-to b3 s1_eu)
      (assigned-to b4 s2_eu)
      (assigned-to b5 s2_eu)
      (online s1_eu)
      (online s2_eu)
      (not (online s3_eu))
    )
  )

  (:metric minimize (total-cost))
)