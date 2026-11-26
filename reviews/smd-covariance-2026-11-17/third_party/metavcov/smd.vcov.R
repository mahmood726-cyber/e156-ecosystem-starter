smd.vcov <- function(nt, nc, d, r, n_rt = NA, n_rc = NA, name = NULL){
  if (length(as.vector(d)) == length(as.matrix(d)[, 1]))   {
    colum.number <- 1}  else {colum.number <- ncol(d)}
  if (length(r) == 1)   {K <- 1} else  { K <- nrow(d)}
  col.vac.number <- (colum.number + 1)*colum.number/2
  if (is.null(name)){
    if (is.null(colnames(d))) {
      name <- paste("g", 1:colum.number, sep = "")
    } else {
      name <- paste("g.",colnames(d), sep = "")
    }
  } else {
    name <- name[1:colum.number]
  }

  cov.name <- c()
  for (i in 1:colum.number){
    if (i == colum.number){ temp <- NULL} else {
      temp <-  paste("cov",name[i], name, sep = "_")[(i+1):colum.number]
    }
    cov.name <- c(cov.name, paste("var", name[i], sep = "_"), temp)
  }

  list.corr.st.varcovar <- list.corr.st.varcovar.d <- list()

  if (is.na(n_rt)&(length(n_rt) == 1)){
    n_rt <- rep(list(matrix(NA, colum.number, colum.number)), K) }

      for (k in 1:K) {
       for (i in 1:colum.number){
        for (j in 1:colum.number){
          if (is.na(n_rt[[k]][i, j]))
            n_rt[[k]][i, j] <- min(nt[k, i], nt[k, j])
        }
      }
     }

  if (is.na(n_rc)&(length(n_rc) == 1)){
    n_rc <- rep(list(matrix(NA, colum.number, colum.number)), K) }

  for (k in 1:K) {
    for (i in 1:colum.number){
      for (j in 1:colum.number){
        if (is.na(n_rc[[k]][i, j]))
          n_rc[[k]][i, j] <- min(nc[k, i], nc[k, j])
      }
    }
  }
    J <- function(x = 1000){1 - 3/(4*x - 1)} ### The function under table 1 in Wei and Higgins (2013);
    ## in section 3.4 in Wei and Higgins (2013),  J <- function(x){gamma(x/2)/sqrt((x/2)*gamma((x-1)/2))}
    g <- d
    colnames(g) <- name
    for (k in 1:K){
      temp <- matrix(NA, colum.number, colum.number)
      colnames(temp) <- rownames(temp) <-  name
      list.corr.st.varcovar[[k]] <- list.corr.st.varcovar.d[[k]] <- temp
      #  i=j=2
      for (i in 1:colum.number){
        for (j in 1:colum.number)
        {
          vi <- nc[k,i] + nt[k,i] - 2
          jvi <- J(vi)
          vj <- nc[k,j] + nt[k,j] - 2
          jvj <- J(vj)
          g[k, i] <- d[k, i]/jvi
          ki <- (2*nt[k, i] - 2)/((nc[k, i] + nt[k, i] - 2)^2) +
                  (2*nc[k, i] - 2)/((nc[k, i] + nt[k, i] - 2)^2)
          kj <- (2*nt[k, j] - 2)/((nc[k, j] + nt[k, j] - 2)^2) +
                  (2*nc[k, j] - 2)/((nc[k, j] + nt[k, j] - 2)^2)
          kij <- 2*(nt[k, i]*nt[k, j]/(nt[k, i] + nt[k, j] - 1) +
                      nc[k, i]*nc[k, j]/(nc[k, i] + nc[k,j] - 1) - 2)/(nc[k, i] + nt[k, i] - 2)/(nc[k, j] + nt[k, j] - 2)
          temp <- (n_rc[[k]][i, j]/nc[k, i]/nc[k, j] +
                     n_rt[[k]][i, j]/nt[k, i]/nt[k, j])*r[[k]][i, j] +
                      kij*((r[[k]][i, j])^2)*d[k, i]*d[k, j]*jvi*jvj*sqrt((vi/(vi - 2) -
                        1/(jvi^2))*(vj/(vj - 2) - 1/(jvj^2)))/sqrt(ki*kj)
          list.corr.st.varcovar[[k]][i, j] <- unlist(temp)

          nT <- max(nt[k, i], nt[k, j])
          nC <- max(nc[k, i], nc[k, j])
          temp <- (nT + nC)*r[[k]][i, j]/nT/nC + ((r[[k]][i, j])^2)*d[k, i]*d[k, j]/2/(nT+nC)
          list.corr.st.varcovar.d[[k]][i, j] <- unlist(temp)
        }
      }
    }
    corr.st.varcovar <- matrix(unlist(lapply(1:K, function(k){
         smTovec(list.corr.st.varcovar[[k]])})), K, col.vac.number, byrow = TRUE)
    corr.st.varcovar.d <- matrix(unlist(lapply(1:K, function(k){
         smTovec(list.corr.st.varcovar.d[[k]])})), K, col.vac.number, byrow = TRUE)
    colnames(corr.st.varcovar) <- colnames(corr.st.varcovar.d) <- cov.name
    list(ef = as.data.frame(g),
         list.vcov = list.corr.st.varcovar,
         matrix.vcov = corr.st.varcovar,
         list.dvcov = list.corr.st.varcovar.d,
         matrix.dvcov = corr.st.varcovar.d)
  }
