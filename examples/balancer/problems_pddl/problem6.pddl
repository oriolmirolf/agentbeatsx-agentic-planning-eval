(define (problem loadbalance-p06)
  (:domain loadbalance)

  (:objects
    us_east - region
    payments search - service
    s1_us s2_us - server
    b1 b2 b3 b4 - bucket
  )

  (:init
    (= (total-cost) 0)
    (server-region s1_us us_east)
    (server-region s2_us us_east)

    (bucket-region b1 us_east)
    (bucket-region b2 us_east)
    (bucket-region b3 us_east)
    (bucket-region b4 us_east)

    (bucket-service b1 payments)
    (bucket-service b2 payments)
    (bucket-service b3 search)
    (bucket-service b4 search)

    (online s1_us)
    (online s2_us)

    (runs s1_us payments)
    (runs s2_us search)

    (assigned-to b1 s1_us)
    (assigned-to b2 s1_us)
    (assigned-to b3 s2_us)
    (unassigned b4)

    ;; --- FIX: INCREASE CAPACITY TO 4 ---
    (= (capacity s1_us) 4) 
    (= (capacity s2_us) 3)

    (= (load s1_us) 2)
    (= (load s2_us) 1)
  )

  ;; Goal: all buckets on s1_us; s2_us powered off
  (:goal
    (and
      (assigned-to b1 s1_us)
      (assigned-to b2 s1_us)
      (assigned-to b3 s1_us)
      (assigned-to b4 s1_us)
      (online s1_us)
      (not (online s2_us))
    )
  )

  (:metric minimize (total-cost))
)