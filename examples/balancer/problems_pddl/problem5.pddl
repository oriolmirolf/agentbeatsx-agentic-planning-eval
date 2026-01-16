(define (problem loadbalance-p05)
  (:domain loadbalance)

  (:objects
    us_east eu_west - region
    search - service
    s1_us - server
    s2_eu s3_eu - server
    b1 b2 b3 b4 - bucket
  )

  (:init
    (= (total-cost) 0)
    (server-region s1_us us_east)
    (server-region s2_eu eu_west)
    (server-region s3_eu eu_west)

    (bucket-region b1 us_east)
    (bucket-region b2 us_east)
    (bucket-region b3 eu_west)
    (bucket-region b4 eu_west)

    (bucket-service b1 search)
    (bucket-service b2 search)
    (bucket-service b3 search)
    (bucket-service b4 search)

    (online s1_us)
    (online s2_eu)
    (not (online s3_eu))

    (runs s1_us search)
    (runs s2_eu search)

    ;; initial assignments
    (assigned-to b1 s1_us)  ; correct
    (assigned-to b3 s1_us)  ; wrong region
    (unassigned b2)
    (unassigned b4)

    (= (capacity s1_us) 3)
    (= (capacity s2_eu) 2)
    (= (capacity s3_eu) 2)

    (= (load s1_us) 2)
    (= (load s2_eu) 0)
    (= (load s3_eu) 0)
  )

  ;; Canonical goal: b1,b2 on s1_us (us_east), b3,b4 on s2_eu (eu_west)
  (:goal
    (and
      (assigned-to b1 s1_us)
      (assigned-to b2 s1_us)
      (assigned-to b3 s2_eu)
      (assigned-to b4 s2_eu)
    )
  )

  (:metric minimize (total-cost))
)