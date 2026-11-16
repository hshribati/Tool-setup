locals {
  # One entry per tier. Resources use this map with for_each.
  tiers = {
    weather = { listener_port = 8080 }
    advisor = { listener_port = 8081 }
  }

  app_port = 3000
}
