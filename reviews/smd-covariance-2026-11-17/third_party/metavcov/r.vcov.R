rToz <- function(x) 0.5*log((1 + x)/(1 - x))
smTovec <- function(x) { as.vector(x[lower.tri(x, diag = TRUE)])}

vecTosm <- function (vec, diag = FALSE)
{
  n = (sqrt(1 + 8 * length(vec)) + 1)/2
  if (diag == TRUE)
    n <- n - 1
  if (ceiling(n) != floor(n))
    stop("Length of vector incompatible with symmetric matrix")
  m <- matrix(NA, nrow = n, ncol = n)
  lo <- lower.tri(m, diag)

  m[lo] <- vec

  for (i in 1:(n - 1)) for (j in (i + 1):n) m[i, j] <- m[j, i]
  return(m)
}

r.vcov <- function(n, corflat,
                   zscore = FALSE, name = NULL,
                   method = "average", na.impute = NA)
{
  if (zscore == TRUE) {corflat <- tanh(corflat)}
  colum.number <- ncol(corflat)

  if (is.null(name)){
    if (is.null(colnames(corflat))) {
      name <- paste("C", 1:colum.number, sep = "")
    } else {
      name <- colnames(corflat)
    }
  } else {
    name <- name[1:colum.number]
  }
  colnames(corflat) <- name

  cov.name <- c()
  for (i in 1:colum.number){
    if (i == colum.number){ temp <- NULL} else {
      temp <-  paste("cov",name[i], name, sep = "_")[(i+1):colum.number]
    }
    cov.name <- c(cov.name, paste("var", name[i], sep = "_"), temp)
  }

  V <- round(sqrt(2*colum.number + 1/4) + 0.5,0)

  if (length(n) == 1)
  {K <- 1}
  else
  { K <- nrow(corflat)}

  temp <- unlist(lapply(1:colum.number, function(i){
            weighted.mean(corflat[, i], n, na.rm = TRUE)}))
  corflat.m <- matrix(rep(temp, K), K, colum.number, byrow = "TRUE")

  if (is.na(na.impute)) {
    corflat[is.na(corflat)] <- na.impute
      } else if (na.impute == "average") {
        corflat[is.na(corflat)] <- corflat.m[is.na(corflat)]} else {
             corflat[is.na(corflat)] <- na.impute }
  rr.corflat <- corflat

  col.vac.number <- (colum.number+1)*colum.number/2
  rcov <- matrix(NA, K, col.vac.number)
  list.rcov <- list()

  zcov <- matrix(NA, K, col.vac.number)
  list.zcov <- list()
  zz.corflat <- corflat
  for (i in 1:K){
    for (j in 1:colum.number)
    {
      zz.corflat[i, j] <- 0.5*log((1 + corflat[i, j])/(1 - corflat[i, j]))
    }
  }

  if (method == "each")
  {corflat <- corflat
   z.corflat <- zz.corflat
  }

  if (method == "average"){
    corflat <- corflat.m

    temp <- unlist(lapply(1:colum.number, function(i, corflat,n){
      weighted.mean(corflat[,i], n, na.rm = TRUE)}, corflat = zz.corflat, n = n))
    z.corflat <- matrix(rep(temp, K), K, colum.number, byrow = "TRUE")
  }

  sum <- 0
  iii <- 1
  foot <- matrix(NA, colum.number, 2)
  f <- NA
  for (ii in 1:(V-1))
  {
    f[ii] <- (V-ii)
    foot[((sum(f) - f[ii] + 1):(sum(f))), 1] <- c(((ii + 1):V))
    foot[((sum(f) - f[ii] + 1):(sum(f))), 2] <- ii

  }

  sub <- as.data.frame(matrix(NA, col.vac.number, 4))
  d <- colum.number
  colnames(sub) <- c("s","t","u","v")
  for (t in 1:(V-1))
  {
    for (s in (t+1):V)
    {
      sub[((sum + 1):(sum + d)), 1] <- s
      sub[((sum + 1):(sum + d)), 2] <- t
      sub[((sum + 1):(sum + d)), 3] <- foot[((colum.number - d + 1):colum.number), 1]
      sub[((sum + 1):(sum + d)), 4] <- foot[((colum.number - d + 1):colum.number), 2]
      sum <- sum+d
      d <- d - 1

    }
  }

  for (k in 1:K)
  {
    r <- vecTosm(t(corflat[k, ]), diag = FALSE)
    diag(r) <- 1

    if (is.na(na.impute)) { corflat[is.na(corflat)] <- na.impute }
    else if (na.impute == "average"){
      r[is.na(r)] <- vecTosm(t(corflat.m[k, ]), diag = FALSE)[is.na(r)]
    } else { r[is.na(r)] <- na.impute }

    for  (ii in 1:col.vac.number)
    {

      rcov[k, ii] <- (0.5*r[sub[ii,]$s,sub[ii,]$t]*r[sub[ii,]$u, sub[ii,]$v]*((r[sub[ii,]$s,sub[ii,]$u])^2
                                                                                      + (r[sub[ii,]$s,sub[ii,]$v])^2
                                                                                      + (r[sub[ii,]$t,sub[ii,]$u])^2+(r[sub[ii,]$t,sub[ii,]$v])^2)
                      + r[sub[ii,]$s,sub[ii,]$u]*r[sub[ii,]$t,sub[ii,]$v]
                               + r[sub[ii,]$s, sub[ii,]$v]*r[sub[ii,]$t, sub[ii,]$u]
                               - (r[sub[ii,]$s, sub[ii,]$t]*r[sub[ii,]$s, sub[ii,]$u]*r[sub[ii,]$s, sub[ii,]$v]
                                 + r[sub[ii,]$t, sub[ii,]$s]*r[sub[ii,]$t, sub[ii,]$u]*r[sub[ii,]$t, sub[ii,]$v]
                                 + r[sub[ii,]$u, sub[ii,]$s]*r[sub[ii,]$u, sub[ii,]$t]*r[sub[ii,]$u, sub[ii,]$v]
                                 + r[sub[ii,]$v, sub[ii,]$s]*r[sub[ii,]$v, sub[ii,]$t]*r[sub[ii,]$v, sub[ii,]$u]))/n[k]
    }

    for  (ii in 1:col.vac.number)
    {
      zcov[k, ii] <- rcov[k, ii]/(1 - (r[sub[ii,]$s,sub[ii,]$t])^2)/(1 - (r[sub[ii,]$u,sub[ii,]$v])^2)
    }

    list.rcov[[k]] <- vecTosm(rcov[k,], diag = TRUE)
    colnames(list.rcov[[k]]) <- rownames(list.rcov[[k]]) <- name


    list.zcov[[k]] <- vecTosm(zcov[k,], diag = TRUE)
  }

  temp <- list.zcov
  list.zcov <- lapply(1:K, function(k){
                 tempp <- diag(temp[[k]])
                 diag(temp[[k]]) <- tempp*(n[k]/(n[k] - 3))  # confirm this is the same as 1/(n[k] - 3)
                 colnames(temp[[k]]) <- rownames(temp[[k]]) <- name
                 temp[[k]]})

  zcov <- matrix(unlist(lapply(1:K, function(k){
            smTovec(list.zcov[[k]])})), K, col.vac.number, byrow = TRUE)

  colnames(rcov) <- colnames(zcov) <- cov.name

  return(list(r = as.data.frame(rr.corflat),
              list.rvcov = list.rcov,
              matrix.rvcov = rcov,
              ef = as.data.frame(zz.corflat),
              matrix.vcov = zcov,
              list.vcov = list.zcov))
}
